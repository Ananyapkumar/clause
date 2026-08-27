"""Extract structured data from lighting product datasheets.

Project 1. Nine fields, validated by Pydantic, with retry on schema
failure and full cost/latency measurement on every run.

Run directly:   py extract.py
Or import:      from extract import extract
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, ValidationError

from schema import LightingDatasheet, build_json_schema
from verify import count_filled_fields, verify_citations

load_dotenv()

# MODEL is read from .env so it can be changed without editing code.
# Add a line to .env:   GEMINI_MODEL=gemini-2.5-flash-lite
# The fallback is used when that line is absent.
#
# Free-tier daily quotas differ enormously between models - Flash was cut
# to 20 requests/day, while Flash-Lite has historically allowed far more.
# Since every result is tagged with the model that produced it, switching
# is safe as long as comparisons are made within a single model.
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MAX_ATTEMPTS = 3
LOG_FILE = "requests.jsonl"

# RATE LIMITS - free tier is 20 requests per DAY on this model.
#
# Google reduced the free Flash quota from 250 RPD to 20 RPD. The 429 message
# says "Please retry in ~52s", which is misleading: a DAILY counter does not
# reset in a minute. Waiting is only useful for a per-minute limit.
#
# So: retry twice with a capped wait (covers per-minute limits), then stop and
# say plainly that the daily quota is gone. Better to fail in 3 minutes with a
# clear message than to burn 10 minutes on something that cannot succeed.
RATE_LIMIT_RETRIES = 2
MAX_WAIT_SECONDS = 90

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

    # Citation verification - added Day 10. Costs nothing; it is a string
    # search against the source document, not another API call.
    citations_total: int = 0
    citations_verified: int = 0
    citations_unverified: list = []
    fields_filled: int = 0


client = genai.Client()


# =============================================================
# THE PROMPT - split in two, so the domain rules can be removed
# =============================================================
# The central claim of this project is:
#
#   "Encoding domain disambiguation rules explicitly in the prompt is
#    sufficient for the model to navigate traps it would otherwise
#    fall into."
#
# On Day 6 the model scored 9/9 on E01, a document containing four
# deliberate traps. That looked like evidence. It was not, because there
# was no control - the model may have succeeded BECAUSE the rules were
# present, or it may have succeeded anyway. Nothing distinguished those.
#
# So the prompt is split. GENERIC_RULES are formatting instructions any
# extraction task would need. DOMAIN_RULES are the lighting judgements
# that came from a domain expert. Running with and without DOMAIN_RULES
# measures what the domain knowledge is worth, in accuracy points.

BASE_INSTRUCTION = "Extract the specified fields from this lighting product datasheet."

# Formatting only. No lighting knowledge. Present in BOTH conditions,
# so the ablation isolates domain knowledge rather than also removing
# instructions about output format.
GENERIC_RULES = """- Numbers must be bare: 4940, not "4,940" and not "4940 lm".
- If a value is genuinely absent from the document, return null.
  Do not infer, calculate, or estimate it."""

# Only added when citations are switched on. Kept separate so the default
# prompt is exactly what produced the 98.4% baseline.
CITATION_RULE = """- For EVERY value you extract, add the exact line from the datasheet you
  read it from to citations, copied character for character. Never leave
  citations empty."""

# The variable under test. Every line here is a lighting-industry
# judgement that the model cannot be assumed to know.
DOMAIN_RULES = """- wattage_w must be SYSTEM wattage (total power draw including driver
  losses). If the datasheet also gives LED load or LED module power,
  do NOT use that.
- luminous_flux_lm must be LUMINAIRE output, not bare LED module output.
- lifespan_hours must be the L80/B10 rated life. Do NOT use the warranty
  period, even if warranty hours are stated more prominently.
- Efficacy figures (lm/W) are NOT wattage and NOT flux. Ignore them
  unless you are certain which field they belong to.
- Where a footnote or note CORRECTS or QUALIFIES a value in a table, the
  footnote takes precedence over the table. This applies to every field,
  not only lifetime figures."""


def build_instructions(
    use_domain_rules: bool = True,
    use_citations: bool = False,
) -> str:
    """Assemble the prompt.

    use_domain_rules=False  -> the ablation
    use_citations=True      -> ask for source quotes (degrades hard documents)
    """
    rules = GENERIC_RULES
    if use_domain_rules:
        rules = DOMAIN_RULES + "\n" + GENERIC_RULES
    if use_citations:
        rules = rules + "\n" + CITATION_RULE

    return f"{BASE_INSTRUCTION}\n\nRULES:\n{rules}\n\nDATASHEET:\n"


# Kept so existing callers still work.
INSTRUCTIONS = build_instructions(use_domain_rules=True)


def _seconds_to_wait(message: str, default: float = 60.0) -> float:
    """Pull the retry delay out of a rate-limit message.

    The API says e.g. "Please retry in 54.550936748s". Reading that is
    better than guessing - too short and you get limited again, too long
    and you waste time.

    re.search finds the first match of a pattern in text. The pattern
    r"retry in ([\\d.]+)s" means: the literal words "retry in", then one
    or more digits-or-dots (captured), then "s".
    """
    match = re.search(r"retry in ([\d.]+)s", message)
    if match:
        # min() caps it - the API sometimes suggests a wait that only makes
        # sense for a per-minute limit, and we do not want to sit for ages.
        return min(float(match.group(1)) + 2, MAX_WAIT_SECONDS)
    return default


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * PRICE_INPUT_PER_1M
        + output_tokens / 1_000_000 * PRICE_OUTPUT_PER_1M
    )


def extract(
    text: str,
    max_attempts: int = MAX_ATTEMPTS,
    use_domain_rules: bool = True,
    use_citations: bool = False,
) -> ExtractionRun:
    """Run one datasheet through the model. Never raises - returns a run.

    use_domain_rules=False removes the lighting-specific disambiguation
    rules from the prompt. That is the ablation: the difference in score
    between the two conditions is what the domain knowledge is worth.
    """
    base_prompt = build_instructions(use_domain_rules, use_citations) + text
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

        # RATE LIMIT HANDLING - added Day 8.
        #
        # The free tier allows 20 requests per minute. A 7-document eval run
        # with retries exceeds that, and the API returns 429. Previously this
        # crashed the whole run mid-way.
        #
        # This also explains the latency mystery logged on Day 6: median
        # latency went 7s -> 41s -> 176s. That was not the model being slow,
        # it was the SDK silently backing off against this same limit.
        #
        # The API tells us how long to wait ("Please retry in 54.5s"), so we
        # read it out of the message rather than guessing.
        interaction = None
        for rate_attempt in range(RATE_LIMIT_RETRIES):
            try:
                interaction = client.interactions.create(
                    model=MODEL,
                    input=prompt,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        # Domain guidance lives in the field descriptions too,
                        # so the ablation must strip those as well as the
                        # prompt rules - otherwise it removes nothing.
                        "schema": build_json_schema(use_domain_rules, use_citations),
                    },
                )
                break                       # success - leave the retry loop
            except Exception as err:
                message = str(err)
                is_rate_limit = "429" in message or "quota" in message.lower()

                # Anything that is not a rate limit is a real error - re-raise.
                if not is_rate_limit:
                    raise

                # Out of retries. Waiting further will not help a daily quota,
                # so stop and say what is actually wrong.
                if rate_attempt == RATE_LIMIT_RETRIES - 1:
                    raise RuntimeError(
                        "Gemini free-tier quota exhausted.\n"
                        "  The free tier allows 20 requests per DAY on this model.\n"
                        "  Waiting will not help - the counter resets at midnight\n"
                        "  Pacific time.\n"
                        "  Options: wait for reset, switch MODEL in extract.py,\n"
                        "  or enable billing (a 7-document eval costs ~$0.003).\n"
                        f"  Original error: {message[:200]}"
                    ) from err

                wait = _seconds_to_wait(message)
                print(f"    [rate limit] waiting {wait:.0f}s (attempt "
                      f"{rate_attempt + 1} of {RATE_LIMIT_RETRIES})...")
                time.sleep(wait)

        if interaction is None:             # defensive; should not happen
            raise RuntimeError("no response after rate-limit retries")

        # Tokens accumulate across retries - 3 attempts costs roughly 3x.
        usage = interaction.usage
        if usage:
            input_tokens += usage.total_input_tokens or 0
            output_tokens += usage.total_output_tokens or 0

        try:
            result = LightingDatasheet.model_validate_json(interaction.output_text)

            # CITATION CHECK - no API call, just a string search against the
            # source document. Free, and it runs on every extraction.
            check = verify_citations(text, result.citations)
            filled = count_filled_fields(result.model_dump())

            return ExtractionRun(
                ok=True,
                result=result,
                attempts=attempt,
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=estimate_cost(input_tokens, output_tokens),
                citations_total=check["total_citations"],
                citations_verified=check["verified"],
                citations_unverified=check["unverified_details"],
                fields_filled=filled,
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
