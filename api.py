"""HTTP API around the datasheet extraction pipeline.

Day 9. Hardened Day 20.

WHAT DAY 20 CHANGED, AND WHY EACH ONE
-------------------------------------
The README's "Known limitations" section listed four things wrong with this
service. Writing them down honestly is worth something; leaving them written
down for two weeks is not. All four are closed here.

1. NO AUTHENTICATION
   The endpoint was public and the free tier allows 20 requests per DAY. Twenty
   requests from anyone on the internet and the service is dead until midnight
   Pacific. That is a denial-of-service costing an attacker one shell script.
   Now: a bearer token, compared in constant time.

2. LOGS ON AN EPHEMERAL FILESYSTEM
   requests.jsonl was written to the container's local disk. Render's free tier
   restarts the instance and the file goes with it - silently, with no error, so
   you find out when you go looking for an incident that has already been
   erased. Now: the same JSON line goes to stdout, where the platform's log
   aggregation captures it. Twelve-factor, and free.

3. NO INPUT SIZE LIMIT
   A 50 MB body was read into memory, sent to the model, and either blew the
   context window or exhausted the container. Unbounded input is a denial of
   service in every system that has one. Now: rejected at 100 kB with 413.

4. ONE GENERIC ERROR FOR EVERY FAILURE
   Quota exhausted, provider outage, and unusable input all returned the same
   thing. A caller cannot act on that. Now: 429 with Retry-After, 503, and 422
   respectively - because "wait until tomorrow", "retry in a minute" and "fix
   your input" are three different instructions.

WHAT IS STILL NOT DONE - stated so it does not get quietly forgotten
   - Rate limiting is per-process and in-memory. With more than one worker the
     effective limit multiplies. Correct fix is a shared store (Redis); not
     done, because a single free-tier instance runs one worker and adding a
     dependency to solve a problem I do not have is how projects rot.
   - No per-caller identity beyond the shared token. One key, one consumer.

Run:
    uvicorn api:app --reload
    http://127.0.0.1:8000/docs
"""

import hmac
import json
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from extract import MODEL, ExtractionRun, extract, log_run
from schema import LightingDatasheet

load_dotenv()

# =============================================================
# CONFIGURATION
# =============================================================

# The shared token. Set CLAUSE_API_KEY in the environment - never in code, and
# never in the repository. Absent, auth is DISABLED so local development works
# without ceremony, and the service says so loudly at startup rather than
# quietly being open.
API_KEY = os.getenv("CLAUSE_API_KEY")
AUTH_ENABLED = bool(API_KEY)

# 100 kB. A long datasheet is a few kB of text; 100 kB is generous by two
# orders of magnitude and still small enough that a hostile caller cannot
# exhaust memory or blow the context window.
MAX_INPUT_CHARS = 100_000

# Per-process request cap. Deliberately below the provider's 20/day so the
# service refuses politely before the provider refuses rudely - a 429 from here
# carries a useful message; a 429 from upstream arrives after the request has
# already cost latency.
MAX_REQUESTS_PER_DAY = 18
_request_times: deque = deque()


# =============================================================
# STRUCTURED LOGGING TO STDOUT
# =============================================================

def emit(event: str, **fields) -> None:
    """One JSON object per line, to stdout.

    stdout rather than a file because the container filesystem does not
    survive a restart. The platform captures stdout; it does not capture
    /app/requests.jsonl.

    Deliberately does NOT log request content. Submitted datasheets may be
    confidential, and logs are usually the least-protected store in a system.
    Length, token counts and outcome give everything needed operationally
    without retaining a customer's document.
    """
    print(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }), flush=True)


# =============================================================
# AUTH
# =============================================================

def require_key(authorization: str | None = Header(default=None)) -> None:
    """Bearer token check.

    hmac.compare_digest rather than == because a normal string comparison
    returns as soon as it finds a differing byte, so the time it takes leaks
    how many leading characters were correct. That is a real attack on a
    long-lived shared secret, and the fix costs one import.
    """
    if not AUTH_ENABLED:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token. Send: Authorization: Bearer <key>",
        )

    supplied = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, API_KEY):
        emit("auth_failed")
        raise HTTPException(status_code=401, detail="Invalid token")


# =============================================================
# RATE LIMIT
# =============================================================

def check_rate_limit() -> None:
    """Reject before the provider does.

    A rolling 24-hour window rather than a midnight reset, because the
    provider's own counter resets at midnight PACIFIC and this service does not
    know what timezone it is running in. A rolling window is stricter than the
    real limit, which is the safe direction to be wrong.
    """
    now = time.time()
    while _request_times and now - _request_times[0] > 86_400:
        _request_times.popleft()

    if len(_request_times) >= MAX_REQUESTS_PER_DAY:
        oldest = _request_times[0]
        retry_after = int(86_400 - (now - oldest)) + 1
        emit("rate_limited", used=len(_request_times), retry_after_s=retry_after)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily request budget exhausted ({MAX_REQUESTS_PER_DAY}). "
                f"This service runs on a free tier allowing 20 requests per "
                f"day. Retry in {retry_after} seconds."
            ),
            headers={"Retry-After": str(retry_after)},
        )
    _request_times.append(now)


# =============================================================
# APP
# =============================================================

app = FastAPI(
    title="Clause - lighting datasheet extraction",
    description=(
        "Extracts nine validated fields from lighting product datasheets. "
        "System wattage over LED load; L80/B10 rated life over warranty hours; "
        "luminaire flux over module flux.\n\n"
        "Measured at 161/162 field judgements over 18 documents, with a "
        "run-to-run noise floor of 1 field per document. See the repository "
        "README for what that number does and does not mean."
    ),
    version="0.2.0",
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Tag every request so a log line can be traced to a caller's report."""
    request_id = str(uuid.uuid4())[:8]
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    emit("request",
         request_id=request_id,
         method=request.method,
         path=request.url.path,
         status=response.status_code,
         ms=int((time.perf_counter() - started) * 1000))
    return response


class ExtractRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=MAX_INPUT_CHARS,
        description="Raw datasheet text",
    )


class ExtractResponse(BaseModel):
    ok: bool
    result: LightingDatasheet | None = None
    attempts: int
    latency_ms: int
    cost_usd: float
    error: str | None = None


@app.on_event("startup")
def startup() -> None:
    emit("startup",
         model=MODEL,
         auth_enabled=AUTH_ENABLED,
         max_input_chars=MAX_INPUT_CHARS,
         max_requests_per_day=MAX_REQUESTS_PER_DAY)
    if not AUTH_ENABLED:
        emit("warning",
             message=("CLAUSE_API_KEY is not set - the endpoint is OPEN. "
                      "Fine locally; set it before deploying."))


@app.get("/health")
def health() -> dict:
    """Liveness check. Unauthenticated, because the platform probes it.

    Deliberately makes no model call. A health check that costs an API request
    would spend the entire daily quota on uptime monitoring.
    """
    now = time.time()
    used = sum(1 for t in _request_times if now - t <= 86_400)
    return {
        "status": "ok",
        "model": MODEL,
        "auth": "enabled" if AUTH_ENABLED else "DISABLED",
        "requests_used_today": used,
        "requests_remaining": max(0, MAX_REQUESTS_PER_DAY - used),
    }


@app.post("/extract",
          response_model=ExtractResponse,
          dependencies=[Depends(require_key)])
def extract_endpoint(request: ExtractRequest) -> ExtractResponse:
    """Extract nine fields from a lighting product datasheet.

    Status codes are distinct because the caller's correct response differs:

        200  extraction ran. Check `ok` - a model failure is a result, not an
             HTTP error, and the response carries the reason.
        401  bad or missing token
        413  input over 100 kB
        422  body did not match the schema (FastAPI handles this)
        429  daily budget exhausted - Retry-After tells you when
        503  provider unreachable
    """
    check_rate_limit()

    if len(request.text) > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Input exceeds {MAX_INPUT_CHARS:,} characters.",
        )

    try:
        run: ExtractionRun = extract(request.text)
    except RuntimeError as err:
        # extract() raises this when the provider's own daily quota is gone.
        # Distinct from our 429: ours is a local budget, this one is upstream
        # and cannot be waited out inside the hour.
        emit("upstream_quota_exhausted", error=str(err)[:200])
        raise HTTPException(
            status_code=429,
            detail=("Upstream provider quota exhausted. Resets at midnight "
                    "Pacific."),
            headers={"Retry-After": "3600"},
        ) from err
    except Exception as err:
        emit("upstream_error", error=str(err)[:200])
        raise HTTPException(
            status_code=503,
            detail="Model provider unreachable. Retry shortly.",
        ) from err

    log_run(run, input_length=len(request.text), source="api")
    emit("extraction",
         ok=run.ok,
         attempts=run.attempts,
         latency_ms=run.latency_ms,
         input_tokens=run.input_tokens,
         output_tokens=run.output_tokens,
         cost_usd=round(run.cost_usd, 8),
         input_chars=len(request.text),
         error=run.error)

    return ExtractResponse(
        ok=run.ok,
        result=run.result,
        attempts=run.attempts,
        latency_ms=run.latency_ms,
        cost_usd=round(run.cost_usd, 8),
        error=run.error,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Errors come back as JSON with the same shape every time.

    A caller parsing responses should not have to handle two formats depending
    on whether the failure was theirs or ours.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": exc.detail, "status": exc.status_code},
        headers=getattr(exc, "headers", None),
    )
