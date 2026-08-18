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

DOCS_DIR = Path("evals/documents")
TRUTH_DIR = Path("evals/ground_truth")
RESULTS_DIR = Path("results")
VERSION = "v0"


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

print(f"Scoring {len(cases)} case(s) against {MODEL}\n")


# =============================================================
# RUN EVERY CASE
# =============================================================

per_field_hits = {f: 0 for f in FIELDS}
rows = []
failures = []

for case in cases:
    run = extract(case["text"])

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

    rows.append({"id": case["id"], "correct_fields": correct, "total_fields": len(FIELDS),
                 "latency_ms": run.latency_ms, "cost_usd": run.cost_usd})

    if mismatches:
        failures.append({"id": case["id"], "mismatches": mismatches})

    mark = "ok  " if correct == len(FIELDS) else "MISS"
    print(f"  {case['id']}  {mark}  {correct}/{len(FIELDS)} fields  ({run.latency_ms} ms)")
    for m in mismatches:
        print(f"        {m['field']:<18} expected {m['expected']!r:<14} got {m['got']!r}")


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
print("-" * 56)
print(f"  total cost           ${sum(r['cost_usd'] for r in rows):.6f}")
print(f"  median latency       {statistics.median(r['latency_ms'] for r in rows):.0f} ms")
print("=" * 56)
print(f"\n  {len(failures)} case(s) with mismatches -> results/failures.json")

RESULTS_DIR.mkdir(exist_ok=True)

with open(RESULTS_DIR / f"{VERSION}.jsonl", "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps(row) + "\n")

with open(RESULTS_DIR / "failures.json", "w", encoding="utf-8") as f:
    json.dump({
        "version": VERSION,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "summary": {
            "documents": n,
            "field_accuracy": round(field_acc, 4),
            "fully_correct_docs": round(perfect_docs, 4),
            "per_field": {f: round(per_field_hits[f] / n, 4) for f in FIELDS},
        },
        "failures": failures,
    }, f, indent=2)
