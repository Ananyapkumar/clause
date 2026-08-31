"""Does the verifier actually verify, or does it just agree?

Day 18.  REVISED Day 18 after the first version returned a confounded result.

--------------------------------------------------------------------------
WHAT THE FIRST VERSION GOT WRONG - read this before trusting any output
--------------------------------------------------------------------------
The first version injected wattage_w = 200 into e16 (the table value, which the
footnote corrects to 185) and asked whether the verifier would fix it. It did
not. The script printed "VERIFIER IS ANCHORING".

That conclusion was not supported, because of something measured twenty minutes
later: the extractor ITSELF returns 200 on e16 in most runs. Five consecutive
measure_variance runs returned 200 five times out of five.

So the verifier was handed the answer it already believes, and kept it. Two
completely different explanations fit equally well:

    ANCHORING   - it keeps whatever it is shown, regardless of content.
    AGREEMENT   - it independently thinks 200 is right, and said so.

A test that cannot distinguish its own hypotheses is not a test. The design
error was picking the injected value before measuring the model's base rate on
that field - so the injection landed on the model's preferred answer, which is
the one position where the two hypotheses make identical predictions.

--------------------------------------------------------------------------
THE FIX: inject against the model's prior, not with it
--------------------------------------------------------------------------
The diagnostic injection is the value the model does NOT usually produce.

For e16 that is 185 - which is also, inconveniently for intuition, the correct
answer. So the decisive run is:

    py test_anchoring.py e16 --field wattage_w --value 185

    verifier KEEPS 185    -> ANCHORING. It accepted a value against its own
                             prior purely because it was shown it. The Day 17
                             "changed 0 fields" result carries no information.

    verifier CHANGES to 200 -> NOT anchoring. It is exercising independent
                             judgement and overriding the candidate. The pass
                             works as designed; it simply disagrees with the
                             ground truth on this field - which is a different
                             and much more interesting problem.

Note what this means: on THIS document, a verifier behaving correctly will
produce a WRONG answer, and a verifier behaving badly will produce a right one.
Scoring the output against ground truth would grade the two backwards. The
thing being measured is the behaviour, not the score.

--------------------------------------------------------------------------
BASE RATE
--------------------------------------------------------------------------
This script now reads results/variance-<doc>-<version>.json if it exists and
reports how often the extractor independently produced the injected value. That
is the number that makes the result interpretable, and it is the number the
first version did not have.

Run measure_variance.py first. Without a base rate this test is guesswork.

COST: 1 API request. 2 with --with-extract.

Usage:
    py test_anchoring.py e16
        Uses the default injection for the document.

    py test_anchoring.py e16 --field wattage_w --value 185
        The decisive run described above.

    py test_anchoring.py e16 --with-extract
        Run a real extraction first and corrupt one field of its output, so the
        other eight fields are genuine model output rather than ground truth.
        2 API requests.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from schema import FIELDS, LightingDatasheet, values_match
from verify_agent import verify

DOCS_DIR = Path("evals/documents")
TRUTH_DIR = Path("evals/ground_truth")
RESULTS_DIR = Path("results")

# Per-document default injections.
#
# UPDATED after the base rate was measured. The right default is the value the
# model does NOT usually produce, because that is where anchoring and agreement
# make different predictions.
DEFAULT_INJECTIONS = {
    # Extractor returns 200 in ~6 of 8 observed runs. So inject 185.
    "e16": ("wattage_w", 185.0),
}


def load_base_rate(doc_id: str, version: str, field: str):
    """How often did the extractor independently produce each value?

    Returns a Counter keyed by the value, or None if no variance file exists.
    Without this the test result cannot be interpreted - see the module
    docstring for what happened when it was run without one.
    """
    path = RESULTS_DIR / f"variance-{doc_id}-{version}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    observed = [o.get(field) for o in data.get("observations", []) if o]
    if not observed:
        return None
    return Counter(
        float(v) if isinstance(v, (int, float)) else v for v in observed
    )


def main() -> None:
    args = sys.argv[1:]
    doc_id = args[0] if args and not args[0].startswith("--") else "e16"
    version = "v2"

    doc_path = DOCS_DIR / f"{doc_id}.txt"
    truth_path = TRUTH_DIR / f"{doc_id}.json"
    if not doc_path.exists():
        print(f"No document at {doc_path}")
        raise SystemExit(1)
    if not truth_path.exists():
        print(f"No ground truth at {truth_path}.")
        raise SystemExit(1)

    document = doc_path.read_text(encoding="utf-8")
    truth = json.loads(truth_path.read_text(encoding="utf-8"))

    if "--field" in args:
        field = args[args.index("--field") + 1]
        if "--value" not in args:
            print("--field requires --value")
            raise SystemExit(1)
        raw = args[args.index("--value") + 1]
        try:
            injected = float(raw)
        except ValueError:
            injected = raw
    elif doc_id in DEFAULT_INJECTIONS:
        field, injected = DEFAULT_INJECTIONS[doc_id]
    else:
        print(f"No default injection for {doc_id}. Use --field and --value.")
        raise SystemExit(1)

    correct_value = truth.get(field)
    injected_is_correct = values_match(field, injected, correct_value)

    # ---------------------------------------------------------------
    # BASE RATE - what does the extractor do on its own?
    # ---------------------------------------------------------------
    base = load_base_rate(doc_id, version, field)
    injected_key = float(injected) if isinstance(injected, (int, float)) else injected

    print(f"Document:          {doc_id}")
    print(f"Field under test:  {field}")
    print(f"Ground truth:      {correct_value!r}")
    print(f"INJECTED:          {injected!r}"
          f"{'  (this IS the correct answer)' if injected_is_correct else '  (wrong)'}")

    against_prior = None
    if base:
        total = sum(base.values())
        n_injected = base.get(injected_key, 0)
        modal, modal_n = base.most_common(1)[0]
        against_prior = n_injected < modal_n
        print(f"\nExtractor base rate on this field ({total} unassisted runs):")
        for value, count in base.most_common():
            mark = "  <- injected" if value == injected_key else ""
            print(f"    {value!r:<16} {count}/{total}{mark}")
        if against_prior:
            print(f"\n  The injected value is AGAINST the model's prior.")
            print(f"  Anchoring and agreement predict different outcomes here.")
            print(f"  This run is diagnostic.")
        else:
            print(f"\n  WARNING: the injected value IS the model's preferred")
            print(f"  answer. Anchoring and agreement predict the SAME outcome,")
            print(f"  so this run cannot distinguish them. Inject a value the")
            print(f"  model does not usually produce.")
    else:
        print(f"\n  NO BASE RATE AVAILABLE.")
        print(f"  Run:  py measure_variance.py {doc_id}")
        print(f"  Without it, a 'no change' result is uninterpretable - it may")
        print(f"  mean the verifier agrees, or that it agrees with everything.")

    requests_needed = 2 if "--with-extract" in args else 1
    print(f"\nCOST: {requests_needed} API request(s)")

    # ---------------------------------------------------------------
    # BUILD THE CANDIDATE
    # ---------------------------------------------------------------
    if "--with-extract" in args:
        from extract import extract
        print("\nRunning a real extraction first...")
        first = extract(document)
        if not first.ok:
            print(f"Extraction failed: {first.error}")
            raise SystemExit(1)
        candidate_values = first.result.model_dump()
        print(f"  extraction returned {field} = {candidate_values.get(field)!r}")
    else:
        # Every other field set to ground truth, so any change the verifier
        # makes elsewhere is unambiguous damage.
        candidate_values = {f: truth.get(f) for f in FIELDS}

    candidate_values[field] = injected
    candidate = LightingDatasheet(**candidate_values)

    print("\nRunning verification pass...")
    result = verify(document, candidate)

    if not result.ok:
        print(f"Verification failed: {result.error}")
        raise SystemExit(1)

    after = result.verified.model_dump()
    got = after.get(field)
    kept = values_match(field, got, injected)

    print(f"\nVerifier changed {len(result.changed_fields)} field(s):")
    if not result.changed_fields:
        print("  (nothing changed)")
    for c in result.changed_fields:
        print(f"  {c['field']:<20} {c['from']!r}  ->  {c['to']!r}")

    # ---------------------------------------------------------------
    # VERDICT - interpreted against the base rate, not against the score
    # ---------------------------------------------------------------
    print("\n" + "=" * 64)
    print(f"  {field}:  shown {injected!r}  ->  returned {got!r}"
          f"   (ground truth {correct_value!r})")
    print("=" * 64)

    if against_prior is None:
        print("  INCONCLUSIVE - no base rate. See above.")
    elif not against_prior:
        print("  CONFOUNDED - the injected value is the model's own preferred")
        print("  answer, so this outcome is equally consistent with anchoring")
        print("  and with genuine agreement. Re-run injecting a value the")
        print("  model does not usually produce.")
    elif kept:
        print("  ANCHORING.")
        print("  The verifier kept a value it does NOT normally produce, purely")
        print("  because it was shown it. That is confirmation bias, not")
        print("  verification: the pass ratifies its input.")
        print()
        print("  Consequence: 'changed 0 fields' means nothing, and a second")
        print("  pass costs 2x for zero detection. Do not ship it.")
        print()
        print("  Worth testing instead:")
        print("    - blind second pass: extract twice, compare in code, so the")
        print("      verifier never sees the candidate")
        print("    - one narrow question per field rather than nine at once")
        print("    - a different model for the second pass")
    else:
        print("  NOT ANCHORING - the verifier exercised independent judgement.")
        print("  It overrode a value it was shown in favour of its own reading")
        print("  of the document. The pass does detect and change things.")
        print()
        if not values_match(field, got, correct_value):
            print("  BUT it moved AWAY from the ground truth. So the verifier")
            print("  works and disagrees with the answer key - which makes this")
            print("  a question about the answer key, not about the verifier.")
            print(f"  See whether {correct_value!r} is genuinely the only")
            print(f"  defensible reading of this document.")

    collateral = [f for f in FIELDS
                  if f != field
                  and not values_match(f, after.get(f), truth.get(f))]
    if collateral:
        print()
        print(f"  DAMAGE: it also broke {len(collateral)} field(s) that were")
        print(f"  correct going in:")
        for f in collateral:
            print(f"    {f:<20} {truth.get(f)!r}  ->  {after.get(f)!r}")
        print("  Verification moves values in BOTH directions. A pass that")
        print("  fixes one field and breaks two is worse than no pass at all.")

    print(f"\n  cost  ${result.cost_usd:.6f}   time  {result.latency_ms} ms")


if __name__ == "__main__":
    main()
