"""HTTP API around the extraction pipeline.

Day 4. Turns extract.py from a script into a service other programs
can call over the network.

Run:
    uvicorn api:app --reload

Then open http://127.0.0.1:8000/docs in a browser.
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from extract import MODEL, ExtractedEmail, ExtractionRun, extract, log_run

# The `app` object IS the service. Everything below attaches to it.
app = FastAPI(
    title="Clause — structured extraction API",
    description="Extracts validated, typed data from unstructured email text.",
    version="0.1.0",
)


# =============================================================
# REQUEST AND RESPONSE SHAPES
# =============================================================
# Same Pydantic idea as Day 2, pointed outward instead of at the model.
# FastAPI uses these to validate incoming requests, shape outgoing
# responses, and generate the /docs page automatically.

class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, description="The raw email text to extract from")


class ExtractResponse(BaseModel):
    ok: bool
    result: ExtractedEmail | None = None
    attempts: int
    latency_ms: int
    cost_usd: float
    error: str | None = None


# =============================================================
# ENDPOINTS
# =============================================================
# An endpoint is one address the service answers on.
# The @app.get / @app.post line above a function is a DECORATOR -
# it registers that function to handle requests at that address.


@app.get("/health")
def health() -> dict:
    """Liveness check. Hosting platforms poll this to see if the app is up."""
    return {"status": "ok", "model": MODEL}


@app.post("/extract", response_model=ExtractResponse)
def extract_endpoint(request: ExtractRequest) -> ExtractResponse:
    """Extract structured information from unstructured email text."""

    # FastAPI has already validated the incoming JSON against
    # ExtractRequest by the time this function runs. A request with a
    # missing or empty `text` never reaches this line - it gets an
    # automatic 422 response instead.
    run: ExtractionRun = extract(request.text)

    # Same logging as the CLI path, tagged so you can tell them apart
    # in requests.jsonl later.
    log_run(run, input_length=len(request.text), source="api")

    return ExtractResponse(
        ok=run.ok,
        result=run.result,
        attempts=run.attempts,
        latency_ms=run.latency_ms,
        cost_usd=round(run.cost_usd, 8),
        error=run.error,
    )
