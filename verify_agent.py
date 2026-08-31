"""Second-pass verification: check the extraction against the document.

Day 17.

THE IDEA
--------
Pass 1 extracts. Pass 2 is shown the document AND pass 1's answers, and asked
one question per field: does the document actually support this value?

This is not the same as asking the model to extract twice and compare. It is a
different task - CHECKING is easier than PRODUCING, because the candidate answer
is already on the page and the model only has to confirm or refute it.

WHY IT MIGHT WORK
-----------------
Day 16 found the model handled footnote precedence correctly for lifespan and
incorrectly for wattage IN THE SAME DOCUMENT. That is inconsistency, not
inability. A second pass gets an independent sample of the same judgement, and
an independent sample of an inconsistent process disagrees with itself often
enough to be informative.

WHY IT MIGHT NOT
----------------
- It doubles cost and latency. Exactly 2x requests.
- The verifier shares the first pass's blind spots. If the model systematically
  misreads something, it will misread it the same way twice.
- It can "correct" a right answer to a wrong one. Verification is not free
  accuracy - it can move fields in both directions, and BOTH directions must be
  measured.

THE MEASUREMENT THAT MATTERS
----------------------------
Not "did accuracy improve" but:

    fields corrected right -> wrong    (verification made it worse)
    fields corrected wrong -> right    (verification helped)
    fields left alone

If it flips as many correct answers as it fixes, it is 2x cost for nothing.

Usage:
    py verify_agent.py e16          one document, prints the comparison
"""

import json
from typing import Optional

from pydantic import BaseModel, ValidationError

from extract import (MODEL, ExtractionRun, _seconds_to_wait, client,
                     estimate_cost, extract)
from schema import FIELDS, LightingDatasheet, build_json_schema, values_match

MAX_ATTEMPTS = 2


class VerificationResult(BaseModel):
    """What the second pass produces."""

    ok: bool
    verified: Optional[LightingDatasheet] = None
    changed_fields: list = []
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: Optional[str] = None


VERIFY_INSTRUCTIONS = """You are checking an extraction that has already been
performed on the datasheet below. Another system produced the CANDIDATE VALUES.

Your job is to check each field against the document, not to re-extract from
scratch. For each field ask: does this document actually support this value?

RULES - the same domain rules the extraction was meant to follow:
- wattage_w must be SYSTEM wattage (total power draw including driver losses),
  never LED load or LED module power.
- luminous_flux_lm must be LUMINAIRE output, never bare LED module output.
- lifespan_hours must be the L80/B10 rated life, never the warranty period and
  never L70/B50.
- Efficacy figures (lm/W) are neither wattage nor flux.
- Where a footnote or note CORRECTS or QUALIFIES a table value, the footnote
  takes precedence over the table. This applies to every field.
- Normalise obvious OCR damage in numeric fields (lowercase-L for 1, capital-O
  for 0, "rn" for "m"), but reproduce model_number exactly as printed.
- If a value is genuinely absent from the document, the correct answer is null.

Return the complete corrected set of nine fields. Where the candidate value is
already correct, return it unchanged. Change a value ONLY when the document
clearly contradicts it - do not change a field because you would have phrased it
differently.

CANDIDATE VALUES:
{candidate}

DATASHEET:
{document}
"""


def verify(document: str, candidate: LightingDatasheet) -> VerificationResult:
    """Run the second pass. Never raises - returns a result."""
    import time

    candidate_json = candidate.model_dump_json(indent=2)
    prompt = VERIFY_INSTRUCTIONS.format(
        candidate=candidate_json, document=document
    )

    started = time.perf_counter()
    input_tokens = 0
    output_tokens = 0
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            interaction = client.interactions.create(
                model=MODEL,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": build_json_schema(True, False),
                },
            )
        except Exception as err:
            message = str(err)
            if "429" in message or "quota" in message.lower():
                raise
            last_error = message
            continue

        usage = interaction.usage
        if usage:
            input_tokens += usage.total_input_tokens or 0
            output_tokens += usage.total_output_tokens or 0

        try:
            checked = LightingDatasheet.model_validate_json(
                interaction.output_text
            )
        except ValidationError as err:
            last_error = str(err)
            continue

        # Which fields did the second pass actually change?
        before = candidate.model_dump()
        after = checked.model_dump()
        changed = [
            {"field": f, "from": before.get(f), "to": after.get(f)}
            for f in FIELDS
            if before.get(f) != after.get(f)
        ]

        return VerificationResult(
            ok=True,
            verified=checked,
            changed_fields=changed,
            latency_ms=int((time.perf_counter() - started) * 1000),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost(input_tokens, output_tokens),
        )

    return VerificationResult(
        ok=False,
        latency_ms=int((time.perf_counter() - started) * 1000),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=estimate_cost(input_tokens, output_tokens),
        error=last_error,
    )


def extract_and_verify(document: str) -> tuple:
    """Both passes. Returns (first_pass_run, verification_result).

    Costs exactly 2 API requests per document, before any retries.
    """
    first = extract(document)
    if not first.ok:
        return first, VerificationResult(ok=False, error="first pass failed")
    second = verify(document, first.result)
    return first, second


if __name__ == "__main__":
    import sys
    from pathlib import Path

    doc_id = sys.argv[1] if len(sys.argv) > 1 else "e16"
    document = Path(f"evals/documents/{doc_id}.txt").read_text(encoding="utf-8")

    print(f"Document: {doc_id}")
    print("Cost: 2 API requests\n")

    first, second = extract_and_verify(document)

    if not first.ok:
        print(f"First pass failed: {first.error}")
        raise SystemExit(1)

    print("PASS 1 (extract):")
    print(json.dumps(first.result.model_dump(exclude={"citations"}), indent=2))

    if not second.ok:
        print(f"\nVerification failed: {second.error}")
        raise SystemExit(1)

    print(f"\nPASS 2 (verify) changed {len(second.changed_fields)} field(s):")
    if not second.changed_fields:
        print("  (nothing changed - the verifier agreed with the extraction)")
    for c in second.changed_fields:
        print(f"  {c['field']:<20} {c['from']!r}  ->  {c['to']!r}")

    total_cost = first.cost_usd + second.cost_usd
    total_ms = first.latency_ms + second.latency_ms
    print(f"\ncost   ${first.cost_usd:.6f} + ${second.cost_usd:.6f} "
          f"= ${total_cost:.6f}")
    print(f"time   {first.latency_ms} + {second.latency_ms} = {total_ms} ms")

    # Compare against ground truth if it exists, so the run is informative
    # rather than just interesting.
    gt_path = Path(f"evals/ground_truth/{doc_id}.json")
    if gt_path.exists():
        truth = json.loads(gt_path.read_text(encoding="utf-8"))
        p1 = first.result.model_dump()
        p2 = second.verified.model_dump()

        def score(values):
            return sum(1 for f in FIELDS
                       if values_match(f, values.get(f), truth.get(f)))

        print(f"\nvs ground truth:  pass 1 {score(p1)}/9   pass 2 {score(p2)}/9")

        wrong = [f for f in FIELDS
                 if not values_match(f, p1.get(f), truth.get(f))]
        if wrong:
            print("  pass 1 wrong on:")
            for f in wrong:
                print(f"    {f:<20} expected {truth.get(f)!r}  got {p1.get(f)!r}")

        for c in second.changed_fields:
            was_right = values_match(c["field"], p1.get(c["field"]),
                                     truth.get(c["field"]))
            now_right = values_match(c["field"], p2.get(c["field"]),
                                     truth.get(c["field"]))
            verdict = ("FIXED" if now_right and not was_right else
                       "BROKE" if was_right and not now_right else
                       "still wrong" if not now_right else "no change")
            print(f"  {c['field']:<20} {verdict}")
