"""Read requests.jsonl and report cost and latency.

Day 4. Logging is only half the job - being able to answer questions
from your logs is the other half.

Run:  py analyze_logs.py
"""

import json
import statistics

LOG_FILE = "requests.jsonl"

# Read the file one line at a time. Each line is an independent JSON
# object, which is what makes JSONL good for logs.
rows = []
with open(LOG_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.strip()          # remove the trailing newline
        if line:                     # skip any blank lines
            rows.append(json.loads(line))

if not rows:
    print("No log entries yet. Send some requests first.")
    raise SystemExit(0)

# Pull out the columns we care about.
latencies = sorted(r["latency_ms"] for r in rows)
costs = [r["cost_usd"] for r in rows]
ok_count = sum(1 for r in rows if r["ok"])
attempts = [r["attempts"] for r in rows]

print(f"runs:            {len(rows)}")
print(f"successful:      {ok_count} / {len(rows)}")
print(f"avg attempts:    {statistics.mean(attempts):.2f}")
print()
print(f"total cost:      ${sum(costs):.6f}")
print(f"cost per run:    ${statistics.mean(costs):.6f}")
print(f"cost per 1,000:  ${sum(costs) / len(rows) * 1000:.2f}")
print()
print(f"median latency:  {statistics.median(latencies):.0f} ms")
print(f"mean latency:    {statistics.mean(latencies):.0f} ms")
print(f"fastest:         {latencies[0]} ms")
print(f"slowest:         {latencies[-1]} ms")
print(f"spread:          {latencies[-1] - latencies[0]} ms")

# Does a longer input mean a slower response? Look and see.
print()
print("input length vs latency:")
print(f"  {'chars':>7}  {'in_tok':>7}  {'out_tok':>7}  {'ms':>7}")
for r in sorted(rows, key=lambda r: r["input_length"]):
    print(f"  {r['input_length']:>7}  {r['input_tokens']:>7}  "
          f"{r['output_tokens']:>7}  {r['latency_ms']:>7}")
