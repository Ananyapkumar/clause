"""Tests for the API layer. ZERO API requests.

Day 20.

WHY THIS COSTS NOTHING
----------------------
The model is stubbed out. That is not a compromise - it is the point.

Everything worth testing here is deterministic: does a bad token get rejected,
does an oversized body get refused, does the budget cap fire, does a provider
outage become a 503 rather than a 500. None of that involves the model, and
running it against the real model would spend the entire daily quota on
questions the model cannot answer.

    "Make the non-deterministic part deterministic and test everything
     around it."

The same principle as agent_graph.py --mock. It means the API layer has a
regression suite that can run on every commit, for free, forever - while the
extraction quality is measured separately by evaluate.py, which costs requests
and therefore runs on demand.

RUN
    py test_api.py

No pytest required; it prints a table and exits non-zero on failure, so it can
be dropped into CI as-is.
"""

import os
import sys
import types
from typing import Optional

from pydantic import BaseModel

os.environ["CLAUSE_API_KEY"] = "test-key-not-a-real-secret"


# =============================================================
# STUBS - installed BEFORE importing api, so api picks these up
# =============================================================
# sys.modules assignment replaces a module before anything imports it. This is
# how the API gets tested without the provider SDK, without a key, and without
# a network. It also means these tests run on a machine that has never had
# credentials - which is what makes them safe to run in CI.

_schema = types.ModuleType("schema")


class LightingDatasheet(BaseModel):
    model_number: Optional[str] = None
    wattage_w: Optional[float] = None


_schema.LightingDatasheet = LightingDatasheet
sys.modules["schema"] = _schema

_extract = types.ModuleType("extract")


class ExtractionRun(BaseModel):
    ok: bool = True
    result: Optional[LightingDatasheet] = None
    attempts: int = 1
    latency_ms: int = 12
    input_tokens: int = 100
    output_tokens: int = 50
    cost_usd: float = 0.0004
    error: Optional[str] = None


_extract.ExtractionRun = ExtractionRun
_extract.MODEL = "stub-model"
_extract.extract = lambda text: ExtractionRun(
    result=LightingDatasheet(model_number="STUB-1", wattage_w=18)
)
_extract.log_run = lambda *a, **k: None
sys.modules["extract"] = _extract

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402

client = TestClient(api.app)
AUTH = {"Authorization": "Bearer test-key-not-a-real-secret"}


def run_tests() -> int:
    checks = []

    # ---- health: unauthenticated, and must not cost a request ----
    r = client.get("/health")
    checks.append(("health returns 200 without a token", r.status_code == 200))
    checks.append(("health reports auth state", r.json()["auth"] == "enabled"))
    checks.append(("health reports remaining budget",
                   "requests_remaining" in r.json()))

    # ---- auth ----
    r = client.post("/extract", json={"text": "datasheet"})
    checks.append(("no token -> 401", r.status_code == 401))
    checks.append(("error body has the same shape as every other error",
                   r.json().get("ok") is False and "error" in r.json()))

    r = client.post("/extract", json={"text": "d"},
                    headers={"Authorization": "Bearer wrong"})
    checks.append(("wrong token -> 401", r.status_code == 401))

    r = client.post("/extract", json={"text": "datasheet"}, headers=AUTH)
    checks.append(("valid token -> 200", r.status_code == 200))
    checks.append(("response carries the extraction", r.json()["ok"] is True))
    checks.append(("every response is traceable (X-Request-ID)",
                   "X-Request-ID" in r.headers))

    # ---- input size: unbounded input is a denial of service ----
    r = client.post("/extract", json={"text": "a" * (api.MAX_INPUT_CHARS * 2)},
                    headers=AUTH)
    checks.append((f"input over {api.MAX_INPUT_CHARS:,} chars rejected",
                   r.status_code in (413, 422)))

    # ---- budget cap fires before the provider's does ----
    api._request_times.clear()
    for _ in range(api.MAX_REQUESTS_PER_DAY):
        client.post("/extract", json={"text": "d"}, headers=AUTH)
    r = client.post("/extract", json={"text": "d"}, headers=AUTH)
    checks.append((f"budget of {api.MAX_REQUESTS_PER_DAY}/day enforced -> 429",
                   r.status_code == 429))
    checks.append(("429 tells the caller when to come back (Retry-After)",
                   "Retry-After" in r.headers))

    # ---- upstream failures map to distinct, actionable codes ----
    api._request_times.clear()
    original = api.extract

    def outage(text):
        raise ConnectionError("provider down")

    api.extract = outage
    r = client.post("/extract", json={"text": "d"}, headers=AUTH)
    checks.append(("provider unreachable -> 503, not 500",
                   r.status_code == 503))

    def quota_gone(text):
        raise RuntimeError("Gemini free-tier quota exhausted.")

    api.extract = quota_gone
    r = client.post("/extract", json={"text": "d"}, headers=AUTH)
    checks.append(("upstream quota exhausted -> 429", r.status_code == 429))
    api.extract = original

    # ---- local development stays frictionless when no key is set ----
    api.AUTH_ENABLED = False
    api._request_times.clear()
    r = client.post("/extract", json={"text": "d"})
    checks.append(("auth disabled (no CLAUSE_API_KEY) -> open for local dev",
                   r.status_code == 200))
    api.AUTH_ENABLED = True

    print()
    failed = 0
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
        failed += not ok
    print(f"\n  {len(checks) - failed}/{len(checks)} passed")
    print("  0 API requests spent.\n")
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if run_tests() else 0)
