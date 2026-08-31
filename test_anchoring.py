"""Does the verifier actually verify, or does it just agree?

Day 18.

THE PROBLEM WITH DAY 17'S RESULT
--------------------------------
verify_agent.py ran on e16 and pass 2 changed ZERO fields. That was recorded as
"the verifier agreed with the extraction".

It is not evidence of anything, and here is why:

    Pass 1 happened to return the CORRECT value (185).
    So the verifier was shown a right answer and left it alone.

A verifier that leaves right answers alone and a verifier that leaves EVERY
answer alone are indistinguishable from that run. The experiment never tested
the thing it was built to test.

THE MISSING CONTROL
-------------------
Hand the verifier a value that is KNOWN TO BE WRONG and see whether it corrects
it.

  - If it corrects the value -> the verification pass works. It can detect an
    error and fix it, and the zero-change result on Day 17 means the extraction
    was genuinely right.

  - If it confirms the wrong value -> the verifier is ANCHORING. It is disposed
    to agree with whatever candidate it is shown, the zero-change result carries
    no information, and the entire second pass is 2x cost for nothing.

This is a two-request experiment that decides whether a feature stays or goes.
It should have been the first thing run, not the second.

WHAT MAKES IT A FAIR TEST
-------------------------
The injected wrong value must be PLAUSIBLE. Injecting wattage_w = 9999 proves
nothing: the range constraint (le=2000) would reject it before the verifier's
judgement mattered, and an absurd value is easy to reject for reasons unrelated
to reading the document.

So the default injection for e16 is 200 - the number PRINTED IN THE TABLE, which
the footnote then corrects to 185. It is in range, it appears verbatim in the
document, and only the footnote-precedence rule makes it wrong. That is the
hardest fair test available.

COST
----
2 API requests: one to inject-and-verify, and that is it - the extraction pass
is skipped entirely because the candidate is supplied by hand.
Actually 1 request in the default mode. See --with-extract below.

Usage:
    py test_anchoring.py e16
        Inject the wrong value into the pass-1 candidate and run ONLY the
        verifier. 1 API request.

    py test_anchoring.py e16 --field wattage_w --value 200
        Choose the field and the wrong value explicitly.

    py test_anchoring.py e16 --with-extract
        Run a real extraction first, then corrupt one field of its output
        before verifying. 2 API requests. Slightly more realistic, because
        the other eight fields are then genuine model output rather than
        ground truth.
"""

import json
import sys
from pathlib import Path

from schema import FIELDS, LightingDatasheet, values_match
from verify_agent import verify

DOCS_DIR = Path("evals/documents")
TRUTH_DIR = Path("evals/ground_truth")

# Per-document default injections. Each one is a value that APPEARS in the
# document but is wrong under the documented domain rules - the hardest fair
# test, because rejecting it requires applying a rule rather than noticing
# something absurd.
DEFAULT_INJECTIONS = {
    # Table says 200 W; footnote says units supplied after Jan 2026 draw 185 W.
    "e16": ("wattage_w", 200.0),
}


def main() -> None:
    args = sys.argv[1:]
    doc_id = args[0] if args and not args[0].startswith("--") else "e16"

    doc_path = DOCS_DIR / f"{doc_id}.txt"
    truth_path = TRUTH_DIR / f"{doc_id}.json"
    if not doc_path.exists():
        print(f"No document at {doc_path}")
        raise SystemExit(1)
    if not truth_path.exists():
        print(f"No ground truth at {truth_path} - this test needs a known "
              f"correct answer to inject a known wrong one.")
        raise SystemExit(1)

    document = doc_path.read_text(encoding="utf-8")
    truth = json.loads(truth_path.read_text(encoding="utf-8"))

    # Which field to corrupt, and what to corrupt it to.
    if "--field" in args:
        field = args[args.index("--field") + 1]
        raw = args[args.index("--value") + 1] if "--value" in args else None
        if raw is None:
            print("--field requires --value")
            raise SystemExit(1)
        try:
            wrong_value = float(raw) if "." in raw or raw.isdigit() else raw
        except ValueError:
            wrong_value = raw
    elif doc_id in DEFAULT_INJECTIONS:
        field, wrong_value = DEFAULT_INJECTIONS[doc_id]
    else:
        print(f"No default injection for {doc_id}.")
        print(f"Pick one yourself, e.g.:")
        print(f"  py test_anchoring.py {doc_id} --field wattage_w --value 200")
        print(f"\nChoose a value that APPEARS in the document but is wrong "
              f"under the domain rules.")
        print(f"An absurd value tests the range constraint, not the verifier.")
        raise SystemExit(1)

    correct_value = truth.get(field)

    if values_match(field, wrong_value, correct_value):
        print(f"The injected value {wrong_value!r} MATCHES ground truth "
              f"{correct_value!r}.")
        print("That is not a wrong answer, so this test would prove nothing.")
        raise SystemExit(1)

    requests_needed = 2 if "--with-extract" in args else 1

    print(f"Document:        {doc_id}")
    print(f"Field under test: {field}")
    print(f"Ground truth:     {correct_value!r}")
    print(f"INJECTED (wrong): {wrong_value!r}")
    print(f"COST:             {requests_needed} API request(s)\n")

    # ---------------------------------------------------------------
    # BUILD THE CANDIDATE the verifier will be shown.
    # ---------------------------------------------------------------
    if "--with-extract" in args:
        from extract import extract
        print("Running a real extraction first...")
        first = extract(document)
        if not first.ok:
            print(f"Extraction failed: {first.error}")
            raise SystemExit(1)
        base = first.result.model_dump()
        print(f"  extraction returned {field} = {base.get(field)!r}")
    else:
        # Start from ground truth so every OTHER field is correct. This
        # isolates the test: the verifier is shown eight right answers and
        # one wrong one, so any change it makes is attributable.
        base = {f: truth.get(f) for f in FIELDS}

    base[field] = wrong_value
    candidate = LightingDatasheet(**base)

    # ---------------------------------------------------------------
    # RUN THE VERIFIER.
    # ---------------------------------------------------------------
    print("\nRunning verification pass...")
    result = verify(document, candidate)

    if not result.ok:
        print(f"Verification failed: {result.error}")
        raise SystemExit(1)

    after = result.verified.model_dump()
    got = after.get(field)
    corrected = values_match(field, got, correct_value)

    print(f"\nVerifier changed {len(result.changed_fields)} field(s):")
    if not result.changed_fields:
        print("  (nothing changed)")
    for c in result.changed_fields:
        print(f"  {c['field']:<20} {c['from']!r}  ->  {c['to']!r}")

    # ---------------------------------------------------------------
    # THE VERDICT.
    # ---------------------------------------------------------------
    print("\n" + "=" * 62)
    print(f"  {field}:  shown {wrong_value!r}  ->  returned {got!r}"
          f"   (correct is {correct_value!r})")
    print("=" * 62)

    if corrected:
        print("  VERIFIER WORKS.")
        print("  It was shown a plausible wrong value that appears in the")
        print("  document, and it corrected it. The zero-change result on")
        print("  Day 17 therefore means the extraction was genuinely right,")
        print("  not that the verifier rubber-stamps its input.")
        print()
        print("  Next question: what does it cost in the other direction?")
        print("  Run it across the eval set and count BROKE as well as FIXED.")
    else:
        print("  VERIFIER IS ANCHORING.")
        print("  It confirmed a value that is wrong under the domain rules and")
        print("  that the document itself corrects in a footnote.")
        print()
        print("  Consequence: the Day 17 'changed 0 fields' result carries no")
        print("  information. A second pass that agrees with whatever it is")
        print("  shown is 2x cost and 2x latency for zero detection.")
        print()
        print("  Do NOT ship it. Options worth testing instead:")
        print("    - blind second pass (extract twice, compare in code) so the")
        print("      verifier is never shown the candidate at all")
        print("    - one narrow question per field instead of nine at once")
        print("    - a different model for the second pass")

    # Did the verifier damage any of the eight correct fields?
    collateral = [f for f in FIELDS
                  if f != field
                  and not values_match(f, after.get(f), truth.get(f))]
    if collateral:
        print()
        print(f"  WARNING - it also broke {len(collateral)} field(s) that were "
              f"correct going in:")
        for f in collateral:
            print(f"    {f:<20} {truth.get(f)!r}  ->  {after.get(f)!r}")
        print("  Verification moves values in BOTH directions. A pass that")
        print("  fixes one field and breaks two is worse than no pass at all.")

    print(f"\n  cost  ${result.cost_usd:.6f}   time  {result.latency_ms} ms")


if __name__ == "__main__":
    main()
