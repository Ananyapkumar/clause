"""Extract structured data from lighting product datasheets.

Project 1. Nine fields, validated by Pydantic, with retry on schema
failure and full cost/latency measurement on every run.

Run directly:   py extract.py
Or import:      from extract import extract
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, ValidationError

from schema import LightingDatasheet

load_dotenv()

MODEL = "gemini-3.6-flash"
MAX_ATTEMPTS = 3
LOG_FILE = "requests.jsonl"

# Price per 1M tokens, USD. Free tier costs nothing - this computes what
# it WOULD cost, which is the number an employer asks for.
PRICE_INPUT_PER_1M = 0.30
PRICE_OUTPUT_PER_1M = 2.50


class ExtractionRun(BaseModel):
    """One run: the answer, plus what it cost to get it."""

    ok: bool
    result: Optional[LightingDatasheet] = None
    attempts: int
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error: Optional[str] = None


client = genai.Client()


# The prompt carries the schema decisions explicitly. The model cannot
# guess that "system wattage" beats "LED load" - it has to be told, and
# the same rule has to hold in the ground truth.
INSTRUCTIONS = """Extract the specified fields from this lighting product datasheet.

RULES:
- wattage_w must be SYSTEM wattage (total power draw including driver
  losses). If the datasheet also gives LED load or LED module power,
  do NOT use that.
- luminous_flux_lm must be LUMINAIRE output, not bare LED module output.
- lifespan_hours must be the L80/B10 rated life. Do NOT use the warranty
  period, even if warranty hours are stated more prominently.
- Numbers must be bare: 4940, not "4,940" and not "4940 lm".
- If a value is genuinely absent from the document, return null.
  Do not infer, calculate, or estimate it.
- Efficacy figures (lm/W) are NOT wattage and NOT flux. Ignore them
  unless you are certain which field they belong to.

DATASHEET:
"""


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * PRICE_INPUT_PER_1M
        + output_tokens / 1_000_000 * PRICE_OUTPUT_PER_1M
    )


def extract(text: str, max_attempts: int = MAX_ATTEMPTS) -> ExtractionRun:
    """Run one datasheet through the model. Never raises - returns a run."""
    base_prompt = INSTRUCTIONS + text
    last_error = None

    started = time.perf_counter()
    input_tokens = 0
    output_tokens = 0

    for attempt in range(1, max_attempts + 1):

        prompt = base_prompt
        if last_error:
            prompt = (
                base_prompt
                + "\n\nYour previous response was REJECTED for this reason:\n"
                + f"{last_error}\n\nReturn valid JSON matching the schema exactly."
            )

        interaction = client.interactions.create(
            model=MODEL,
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": LightingDatasheet.model_json_schema(),
            },
        )

        # Tokens accumulate across retries - 3 attempts costs roughly 3x.
        usage = interaction.usage
        if usage:
            input_tokens += usage.total_input_tokens or 0
            output_tokens += usage.total_output_tokens or 0

        try:
            result = LightingDatasheet.model_validate_json(interaction.output_text)
            return ExtractionRun(
                ok=True,
                result=result,
                attempts=attempt,
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=estimate_cost(input_tokens, output_tokens),
            )
        except ValidationError as err:
            last_error = str(err)

    return ExtractionRun(
        ok=False,
        attempts=max_attempts,
        latency_ms=int((time.perf_counter() - started) * 1000),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=estimate_cost(input_tokens, output_tokens),
        error=last_error,
    )


def log_run(run: ExtractionRun, input_length: int, source: str = "cli") -> None:
    """Append one line to requests.jsonl. JSONL = one JSON object per line."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "model": MODEL,
        "input_length": input_length,
        "ok": run.ok,
        "attempts": run.attempts,
        "latency_ms": run.latency_ms,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cost_usd": round(run.cost_usd, 8),
        "error": run.error,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# =============================================================
# DEMO - only runs when you type `py extract.py`
# =============================================================

if __name__ == "__main__":
    doc_path = Path("evals/documents/e01.txt")

    if not doc_path.exists():
        print(f"No document at {doc_path}")
        print("Put a datasheet there first, or run:  py evaluate.py")
        raise SystemExit(1)

    text = doc_path.read_text(encoding="utf-8")
    run = extract(text)
    log_run(run, input_length=len(text))

    print(f"[{'ok' if run.ok else 'fail'}] {run.attempts} attempt(s) | "
          f"{run.latency_ms} ms | {run.input_tokens} in / {run.output_tokens} out | "
          f"${run.cost_usd:.6f}\n")

    if run.result:
        print(run.result.model_dump_json(indent=2))
    else:
        print(f"Failed: {run.error}")
