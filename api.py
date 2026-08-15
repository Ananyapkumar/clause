"""HTTP API around the datasheet extraction pipeline.

Run:
    uvicorn api:app --reload

Then open http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from extract import MODEL, ExtractionRun, extract, log_run
from schema import LightingDatasheet

app = FastAPI(
    title="Clause — lighting datasheet extraction",
    description=(
        "Extracts nine validated fields from lighting product datasheets. "
        "System wattage over LED load; rated life over warranty hours; "
        "luminaire flux over module flux."
    ),
    version="0.1.0",
)


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, description="Raw datasheet text")


class ExtractResponse(BaseModel):
    ok: bool
    result: LightingDatasheet | None = None
    attempts: int
    latency_ms: int
    cost_usd: float
    error: str | None = None


@app.get("/health")
def health() -> dict:
    """Liveness check. Hosting platforms poll this."""
    return {"status": "ok", "model": MODEL}


@app.post("/extract", response_model=ExtractResponse)
def extract_endpoint(request: ExtractRequest) -> ExtractResponse:
    """Extract nine fields from a lighting product datasheet."""
    run: ExtractionRun = extract(request.text)
    log_run(run, input_length=len(request.text), source="api")

    return ExtractResponse(
        ok=run.ok,
        result=run.result,
        attempts=run.attempts,
        latency_ms=run.latency_ms,
        cost_usd=round(run.cost_usd, 8),
        error=run.error,
    )
