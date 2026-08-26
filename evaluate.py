"""Score the extractor against hand-written ground truth.

Project 1, Day 5.

Reads pairs:
    evals/documents/e01.txt        the datasheet   (Claude-generated)
    evals/ground_truth/e01.json    the answer key  (hand-written by me)

Runs every document, compares field by field, prints per-field accuracy,
and writes every disagreement to results/failures.json for review.

Run:  py evaluate.py
"""

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from extract import MODEL, extract
from schema import FIELDS

# Imported lazily inside the run - loading the embedding model is slow and
# pointless when running without retrieval.
build_context = None

import sys

# ABLATION SWITCH
#
#   py evaluate.py                     domain rules IN prompt   -> v0
#   py evaluate.py --no-domain-rules   domain rules REMOVED     -> v0-ablation
#
# The difference between the two scores is what the lighting domain
# knowledge is worth, measured in accuracy points. Without this control
# a high score is unfalsifiable - the model might have succeeded anyway.
USE_DOMAIN_RULES = "--no-domain-rules" not in sys.argv

# REQUEST BUDGET GUARD
#
#   py evaluate.py --limit 2    score only the first 2 documents
#
# Free tier is 20 requests/day and a full run costs 7. When you only need
# to check that a change works, spend 2 requests instead of 7.
# NOTE: a limited run is NOT a baseline. Never publish a --limit score.
LIMIT = None
if "--limit" in sys.argv:
    LIMIT = int(sys.argv[sys.argv.index("--limit") + 1])

# CITATIONS - off by default. See the Day 10 finding in schema.py.
#   py evaluate.py --with-citations
USE_CITATIONS = "--with-citations" in sys.argv

# RETRIEVAL - Day 13.
#   py evaluate.py               whole document in the prompt  -> v0
#   py evaluate.py --retrieval   retrieved chunks only         -> v1
#
# Requires `py ingest.py` to have been run first.
USE_RETRIEVAL = "--retrieval" in sys.argv

DOCS_DIR = Path("evals/documents")
TRUTH_DIR = Path("evals/ground_truth")
RESULTS_DIR = Path("results")
if not USE_DOMAIN_RULES:
    VERSION = "v0-ablation"
elif USE_RETRIEVAL:
    VERSION = "v1-retrieval"
else:
    VERSION = "v0"

# Which fields are which type. Used to validate the ground truth, not just
# the model output - see the type check below.
TEXT_FIELDS = {"model_number", "ip_rating"}
BOOL_FIELDS = {"dimmable"}


# =============================================================
# COMPARING ONE FIELD
# =============================================================
# Deliberately strict. A datasheet value is either right or it isn't -
# there is no "nearly 4940 lumens". The only tolerance allowed is for
# text formatting (case and surrounding spaces) on the two text fields.

def values_match(field: str, predicted, expected) -> bool:
    # null == null is a correct answer: "this document doesn't state it"
    if predicted is None and expected is None:
        return True
    if predicted is None or expected is None:
        return False

    if field in ("model_number", "ip_rating"):
        return str(predicted).strip().upper() == str(expected).strip().upper()

    if field == "dimmable":
        return bool(predicted) == bool(expected)

    # Numeric fields: compare as numbers so 4940 == 4940.0
    try:
        return float(predicted) == float(expected)
    except (TypeError, ValueError):
        return str(predicted).strip() == str(expected).strip()


# =============================================================
# LOAD THE CASES
# =============================================================

if not DOCS_DIR.exists() or not TRUTH_DIR.exists():
    print(f"Expected {DOCS_DIR}/ and {TRUTH_DIR}/ to exist.")
    raise SystemExit(1)

cases = []
missing_truth = []

for doc in sorted(DOCS_DIR.glob("*.txt")):
    case_id = doc.stem                       # "e01.txt" -> "e01"
    truth_file = TRUTH_DIR / f"{case_id}.json"

    if not truth_file.exists():
        missing_truth.append(case_id)
        continue

    truth = json.loads(truth_file.read_text(encoding="utf-8"))

    # A ground-truth file with any field left as the placeholder string
    # is not finished. Better to refuse than to score against a guess.
    placeholders = [k for k, v in truth.items() if v == "FILL_ME_IN"]
    if placeholders:
        missing_truth.append(f"{case_id} (unfilled: {', '.join(placeholders)})")
        continue

    # A key that is ABSENT is not the same as a key set to null.
    # Absent means "I forgot to write this". Null means "the document
    # genuinely does not state it". Reading absent as null silently
    # scores a forgotten field as a deliberate answer - and the model
    # gets marked wrong for being right. Refuse instead.
    absent = [f for f in FIELDS if f not in truth]
    if absent:
        missing_truth.append(f"{case_id} (keys absent: {', '.join(absent)})")
        continue

    # TYPE CHECK - added Day 8, after the third consecutive session where a
    # defect in the ANSWER KEY produced a wrong score and the model was right.
    #
    #   Day 5: a formatting example copied in as ground truth   -> 11.1%
    #   Day 6: two keys deleted from a file                     -> 92.6%
    #   Day 8: units in values, booleans written as strings     -> 90.5%
    #
    # The convention was written down all three times. Writing it down did not
    # work. So the harness enforces it: ground truth is validated the same way
    # model output is, and a badly typed answer key is refused rather than
    # scored against.
    type_errors = []
    for field in FIELDS:
        value = truth[field]
        if value is None:
            continue                          # null is always allowed

        if field in TEXT_FIELDS:
            if not isinstance(value, str):
                type_errors.append(f"{field}={value!r} should be quoted text")

        elif field in BOOL_FIELDS:
            # bool must come before the numeric check: in Python, True IS 1.
            if not isinstance(value, bool):
                type_errors.append(
                    f"{field}={value!r} must be true or false "
                    f"(lowercase, unquoted)"
                )

        else:                                 # numeric fields
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                hint = ""
                if isinstance(value, str):
                    hint = (
                        " - looks like a quoted value; strip the quotes and any unit"
                        if any(c.isdigit() for c in value)
                        else " - not a number"
                    )
                type_errors.append(f"{field}={value!r} must be a bare number{hint}")

    if type_errors:
        detail = "; ".join(type_errors)
        missing_truth.append(f"{case_id} (type errors: {detail})")
        continue

    unknown = [k for k in truth if k not in FIELDS]
    if unknown:
        missing_truth.append(f"{case_id} (unknown keys: {', '.join(unknown)})")
        continue

    cases.append({"id": case_id, "text": doc.read_text(encoding="utf-8"), "truth": truth})

if missing_truth:
    print("Ground truth missing or incomplete for:")
    for m in missing_truth:
        print(f"  - {m}")
    print("\nWrite the answers by hand before scoring. Never let the model")
    print("fill these in - that produces a self-confirming eval set.\n")

if not cases:
    print("No complete cases. Nothing to score.")
    raise SystemExit(1)

if LIMIT:
    cases = cases[:LIMIT]
    print(f"*** LIMITED RUN: first {LIMIT} case(s) only. Not a baseline. ***\n")

if USE_RETRIEVAL:
    print("Loading retrieval index (local, no API calls)...")
    from retrieve import build_context  # noqa: E402  - deliberate lazy import

condition = "WITH domain rules" if USE_DOMAIN_RULES else "WITHOUT domain rules (ABLATION)"
if USE_RETRIEVAL:
    condition += " + RETRIEVAL (chunks only, not full document)"
print(f"Scoring {len(cases)} case(s) against {MODEL}")
print(f"Condition: {condition}  ->  results saved as {VERSION}")
print(f"Budget: this run needs at least {len(cases)} API requests "
      f"(more if any document needs a retry).")
print(f"Free tier allows 20 per day.\n")


# =============================================================
# RUN EVERY CASE
# =============================================================

per_field_hits = {f: 0 for f in FIELDS}
rows = []
failures = []

# Citation totals across the whole run - Day 10.
cite_total = 0
cite_verified = 0
cite_problems = []

for case in cases:
    # RETRIEVAL: replace the full document with only the retrieved chunks.
    # Everything downstream is identical, so any difference in score is
    # attributable to retrieval and nothing else.
    text_to_send = case["text"]
    context_chars = len(text_to_send)
    chunks_used = None

    if USE_RETRIEVAL:
        retrieved = build_context(case["id"])
        text_to_send = retrieved["context"]
        context_chars = retrieved["context_chars"]
        chunks_used = retrieved["chunks_used"]

    run = extract(text_to_send, use_domain_rules=USE_DOMAIN_RULES,
                  use_citations=USE_CITATIONS)

    if not run.ok:
        rows.append({"id": case["id"], "correct_fields": 0, "total_fields": len(FIELDS),
                     "latency_ms": run.latency_ms, "cost_usd": run.cost_usd})
        failures.append({"id": case["id"], "reason": "no valid output after retries",
                         "error": run.error})
        print(f"  {case['id']}  FAIL  no valid output")
        continue

    predicted = run.result.model_dump()
    correct = 0
    mismatches = []

    for field in FIELDS:
        got = predicted.get(field)
        want = case["truth"].get(field)
        if values_match(field, got, want):
            correct += 1
            per_field_hits[field] += 1
        else:
            mismatches.append({"field": field, "expected": want, "got": got})

    # Citation totals for this document.
    cite_total += run.citations_total
    cite_verified += run.citations_verified
    if run.citations_unverified or run.citations_total == 0:
        cite_problems.append({
            "id": case["id"],
            "fields_filled": run.fields_filled,
            "citations_returned": run.citations_total,
            "unverified_citations": run.citations_unverified,
        })

    rows.append({"id": case["id"], "correct_fields": correct, "total_fields": len(FIELDS),
                 "latency_ms": run.latency_ms, "cost_usd": run.cost_usd,
                 "input_tokens": run.input_tokens,
                 "context_chars": context_chars,
                 "chunks_used": chunks_used,
                 "citations_total": run.citations_total,
                 "citations_verified": run.citations_verified})

    if mismatches:
        failures.append({"id": case["id"], "mismatches": mismatches})

    mark = "ok  " if correct == len(FIELDS) else "MISS"
    cite_note = f"cite {run.citations_verified}/{run.citations_total}  " if USE_CITATIONS else ""
    print(f"  {case['id']}  {mark}  {correct}/{len(FIELDS)} fields  "
          f"{cite_note}({run.latency_ms} ms)")
    for m in mismatches:
        print(f"        {m['field']:<18} expected {m['expected']!r:<14} got {m['got']!r}")
    # Only complain about missing citations when citations were asked for.
    if USE_CITATIONS and run.citations_total == 0 and run.fields_filled > 0:
        print(f"        [NO CITATIONS AT ALL] {run.fields_filled} field(s) "
              f"filled, 0 quoted")
    for u in run.citations_unverified:
        print(f"        [HALLUCINATED CITATION] {u['verbatim'][:70]!r}")


# =============================================================
# THE SCORE
# =============================================================

n = len(rows)
total_fields = sum(r["total_fields"] for r in rows)
total_correct = sum(r["correct_fields"] for r in rows)
field_acc = total_correct / total_fields
perfect_docs = sum(1 for r in rows if r["correct_fields"] == r["total_fields"]) / n

print("\n" + "=" * 56)
print(f"  version              {VERSION}")
print(f"  documents            {n}")
print(f"  field accuracy       {field_acc:.1%}   ({total_correct}/{total_fields})")
print(f"  fully correct docs   {perfect_docs:.1%}")
print("-" * 56)
print("  per field:")
for field in FIELDS:
    acc = per_field_hits[field] / n
    bar = "#" * round(acc * 20)
    print(f"    {field:<20} {acc:>6.1%}  {bar}")
cite_rate = cite_verified / cite_total if cite_total else 0.0
hallucination_rate = 1 - cite_rate
if USE_CITATIONS:
    print("-" * 56)
    print(f"  citations            {cite_verified}/{cite_total} verified verbatim")
    print(f"  citation accuracy    {cite_rate:.1%}")
    print(f"  HALLUCINATION RATE   {hallucination_rate:.1%}   "
          f"(cited text not found in source)")
print("-" * 56)
total_ctx = sum(r["context_chars"] for r in rows)
total_in_tokens = sum(r["input_tokens"] for r in rows)
print(f"  context sent         {total_ctx:,} chars, "
      f"{total_in_tokens:,} input tokens")
if USE_RETRIEVAL:
    avg_chunks = statistics.mean(r["chunks_used"] for r in rows)
    print(f"  chunks per document  {avg_chunks:.1f} average")
print("-" * 56)
print(f"  total cost           ${sum(r['cost_usd'] for r in rows):.6f}")
print(f"  median latency       {statistics.median(r['latency_ms'] for r in rows):.0f} ms")
print("=" * 56)
print(f"\n  {len(failures)} case(s) with mismatches -> "
      f"results/failures-{VERSION}.json")

RESULTS_DIR.mkdir(exist_ok=True)

with open(RESULTS_DIR / f"{VERSION}.jsonl", "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row) + "\n")

with open(RESULTS_DIR / f"failures-{VERSION}.json", "w", encoding="utf-8") as f:
    json.dump({
        "version": VERSION,
        "domain_rules_in_prompt": USE_DOMAIN_RULES,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "summary": {
            "documents": n,
            "field_accuracy": round(field_acc, 4),
            "fully_correct_docs": round(perfect_docs, 4),
            "per_field": {f: round(per_field_hits[f] / n, 4) for f in FIELDS},
            "citations_total": cite_total,
            "citations_verified": cite_verified,
            "citation_accuracy": round(cite_rate, 4),
            "hallucination_rate": round(hallucination_rate, 4),
        },
        "failures": failures,
        "citation_problems": cite_problems,
    }, f, indent=2)
