"""Measure the noise floor: run ONE document N times and tally what changes.

Day 18.

WHY THIS EXISTS
---------------
On Day 17 the same document, same prompt, same model returned wattage_w = 200
in the eval run and 185 in verify_agent pass 1. That means the output of this
system is a DISTRIBUTION, not a value, and every score in the project so far is
a single sample from it.

That has a consequence that undoes two days of work:

    v0 scored 161/162.  v2 scored 161/162.
    Both are n=1. A one-field difference sits inside the variation I have now
    directly observed. So "the footnote rule made no difference" is NOT a
    finding - it is an unmeasured comparison.

A noise floor is the fix. It is the amount a metric moves when NOTHING changes.
Once you know it, you know the smallest difference this eval can actually
detect, and every claim you make gets an honest error bar instead of a
decimal point.

WHY NOT JUST RUN `py evaluate.py --only e16` FIVE TIMES
-------------------------------------------------------
Two reasons, and the first one is destructive.

1. evaluate.py writes results/v2.jsonl and results/failures-v2.json at the end
   of EVERY run. Running it five times on a single document would overwrite the
   real 18-document v2 baseline with a 1-document subset run. The baseline is
   not recoverable without spending 18 requests to regenerate it.

2. It prints five separate scores and leaves the tallying to you. What is
   actually wanted is not five numbers but the DISTRIBUTION of each field
   across the five - which value appeared, how often, and which fields were
   stable. Counting that by eye from five terminal screens is how transcription
   errors get into findings.

So this script runs the extraction directly, never touches results/v2.jsonl,
and writes its own file.

WHAT IT COSTS
-------------
Exactly one API request per run, plus any retries. Default 5 runs = 5 requests
out of the 20/day free tier. Nothing else in this file costs anything.

Usage:
    py measure_variance.py e16              5 runs (default)
    py measure_variance.py e16 --runs 3     3 runs
    py measure_variance.py e16 --no-domain-rules    measure v0-ablation instead
"""

import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from extract import MODEL, extract
from schema import FIELDS, values_match

DOCS_DIR = Path("evals/documents")
TRUTH_DIR = Path("evals/ground_truth")
RESULTS_DIR = Path("results")

# Fields that are compared as text rather than as numbers.
TEXT_FIELDS = {"model_number", "ip_rating"}
BOOL_FIELDS = {"dimmable"}


def canonical(field: str, value):
    """Turn a value into something countable, using the SAME rules as scoring.

    Without this, 185 and 185.0 would be counted as two different answers and
    the script would report variation that does not exist. That is exactly the
    bug that made verify_agent.py report 8/9 when the true score was 9/9 - so
    the canonicalisation has to match values_match, not merely resemble it.

    Returns a hashable value suitable for use as a Counter key.
    """
    if value is None:
        return None
    if field in TEXT_FIELDS:
        return str(value).strip().upper()
    if field in BOOL_FIELDS:
        return bool(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value).strip()


def main() -> None:
    args = sys.argv[1:]
    doc_id = args[0] if args and not args[0].startswith("--") else "e16"

    runs = 5
    if "--runs" in args:
        runs = int(args[args.index("--runs") + 1])

    use_domain_rules = "--no-domain-rules" not in args
    version = "v2" if use_domain_rules else "v0-ablation"

    doc_path = DOCS_DIR / f"{doc_id}.txt"
    if not doc_path.exists():
        print(f"No document at {doc_path}")
        raise SystemExit(1)
    document = doc_path.read_text(encoding="utf-8")

    truth_path = TRUTH_DIR / f"{doc_id}.json"
    truth = None
    if truth_path.exists():
        truth = json.loads(truth_path.read_text(encoding="utf-8"))

    print(f"Document:   {doc_id}")
    print(f"Model:      {MODEL}")
    print(f"Condition:  {version}")
    print(f"Runs:       {runs}")
    print(f"COST:       {runs} API requests (more if any run needs a retry)")
    print(f"            Free tier is 20 per DAY.\n")

    # ---------------------------------------------------------------
    # RUN IT N TIMES. Nothing changes between runs. That is the point.
    # ---------------------------------------------------------------
    observations = []      # one dict of field -> value per run
    scores = []            # one score per run, if ground truth exists
    latencies = []
    total_cost = 0.0
    total_requests = 0

    for i in range(1, runs + 1):
        run = extract(document, use_domain_rules=use_domain_rules)
        total_requests += run.attempts
        total_cost += run.cost_usd
        latencies.append(run.latency_ms)

        if not run.ok:
            print(f"  run {i}  FAILED after {run.attempts} attempt(s): "
                  f"{str(run.error)[:80]}")
            observations.append(None)
            scores.append(None)
            continue

        values = run.result.model_dump()
        observations.append({f: values.get(f) for f in FIELDS})

        if truth is not None:
            score = sum(1 for f in FIELDS
                        if values_match(f, values.get(f), truth.get(f)))
            scores.append(score)
            print(f"  run {i}  {score}/{len(FIELDS)} fields  "
                  f"({run.latency_ms} ms, {run.attempts} attempt(s))")
        else:
            scores.append(None)
            print(f"  run {i}  ok  ({run.latency_ms} ms, "
                  f"{run.attempts} attempt(s))")

    good = [o for o in observations if o is not None]
    if len(good) < 2:
        print("\nFewer than 2 successful runs - nothing to compare.")
        raise SystemExit(1)

    # ---------------------------------------------------------------
    # PER-FIELD DISTRIBUTION
    #
    # For each field, count how often each distinct value appeared. A field
    # that returned the same value every time is STABLE. A field that did not
    # is the noise, and it is the only thing on this page that matters.
    # ---------------------------------------------------------------
    print("\n" + "=" * 62)
    print("  PER-FIELD STABILITY")
    print("=" * 62)

    unstable = {}
    for field in FIELDS:
        counts = Counter(canonical(field, o.get(field)) for o in good)
        modal_value, modal_count = counts.most_common(1)[0]
        agreement = modal_count / len(good)

        if len(counts) == 1:
            print(f"  {field:<20} stable    {modal_value!r}")
        else:
            unstable[field] = {
                "distinct_values": len(counts),
                "agreement": round(agreement, 4),
                "counts": {str(k): v for k, v in counts.most_common()},
            }
            spread = "  ".join(f"{k!r} x{v}" for k, v in counts.most_common())
            print(f"  {field:<20} VARIES    {spread}")
            if truth is not None:
                want = truth.get(field)
                right = sum(1 for o in good
                            if values_match(field, o.get(field), want))
                print(f"  {'':<20}           correct in {right}/{len(good)} "
                      f"runs (expected {want!r})")

    # ---------------------------------------------------------------
    # THE NOISE FLOOR
    #
    # This is the number the whole exercise exists to produce: how much the
    # score moves when nothing changes. Any version-to-version difference
    # smaller than this is not a result.
    # ---------------------------------------------------------------
    print("\n" + "=" * 62)
    print("  NOISE FLOOR")
    print("=" * 62)

    real_scores = [s for s in scores if s is not None]
    noise = None
    if real_scores and len(real_scores) >= 2:
        lo, hi = min(real_scores), max(real_scores)
        noise = hi - lo
        mean = statistics.mean(real_scores)
        stdev = statistics.stdev(real_scores) if len(real_scores) > 1 else 0.0
        print(f"  scores               {real_scores}")
        print(f"  range                {lo} to {hi}  (spread {noise} field(s))")
        print(f"  mean                 {mean:.2f}/{len(FIELDS)}")
        print(f"  standard deviation   {stdev:.2f} fields")
        print()
        if noise == 0:
            print("  On this document the score did not move.")
            print("  NOTE: a stable SCORE does not prove stable VALUES - check")
            print("  the per-field section above. Two different wrong answers")
            print("  produce the same score.")
        else:
            print(f"  A difference of {noise} field(s) or fewer between two")
            print(f"  versions on this document is INDISTINGUISHABLE from noise.")
    else:
        print("  No ground truth for this document - scores unavailable.")
        print("  Field stability above is still valid.")

    print("-" * 62)
    print(f"  unstable fields      {len(unstable)} of {len(FIELDS)}")
    if unstable:
        print(f"                       {', '.join(unstable)}")
    print(f"  successful runs      {len(good)} of {runs}")
    print(f"  API requests used    {total_requests}")
    print(f"  cost (list price)    ${total_cost:.6f}")
    print(f"  median latency       {statistics.median(latencies):.0f} ms")
    print("=" * 62)

    # ---------------------------------------------------------------
    # SAVE IT. Separate filename per document and condition, so this can
    # never overwrite the real eval baselines in results/.
    # ---------------------------------------------------------------
    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"variance-{doc_id}-{version}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "document": doc_id,
            "version": version,
            "model": MODEL,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "runs_requested": runs,
            "runs_successful": len(good),
            "api_requests_used": total_requests,
            "scores": scores,
            "noise_floor_fields": noise,
            "unstable_fields": unstable,
            "observations": observations,
        }, f, indent=2)

    print(f"\n  written to {out_path}")
    print("\n  results/v2.jsonl and results/failures-v2.json were NOT touched.")


if __name__ == "__main__":
    main()
