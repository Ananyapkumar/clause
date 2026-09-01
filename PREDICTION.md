# Pre-registration: v2 baseline, 18 documents

**Written and committed BEFORE the run. Day 19.**

## Why this file exists

Day 18 measured the run-to-run variance of this system and produced a model of
it. A model that predicts something is worth more than one that explains
something, so this file states what the next run will produce **before it is
run**.

The reason to commit it first is not ceremony. It is that the alternative —
seeing a number and then explaining why it was expected — is something people do
without noticing. Once the prediction is in git with a timestamp, it cannot be
quietly adjusted to fit.

If the prediction is wrong, that is the useful outcome. It means the variance
model is wrong, and I would rather find that here than in an interview.

---

## The state of the evidence going in

Day 18 measured two documents by repeated identical runs.

| Document | Runs | Field that moved | Correct rate |
|---|---|---|---|
| e16 | 8 | `wattage_w` | 2/8 = **25%** |
| e14 | 5 | `model_number` | 2/5 = **40%** |

All other fields on both documents returned the same value on every run.
Documents e01–e13, e15, e17, e18 have **not** been measured for variance — one
observation each. Their stability is assumed, not established.

---

## The prediction

Treating the two measured fields as independent Bernoulli trials and all other
160 judgements as fixed:

```
P(e16 wattage_w wrong)     = 0.75
P(e14 model_number wrong)  = 0.60

expected wrong   = 0.75 + 0.60                = 1.35 fields
expected score   = 162 - 1.35                 = 160.65 / 162
variance         = 0.75(0.25) + 0.60(0.40)    = 0.4275
standard dev     = sqrt(0.4275)               = 0.65 fields
```

### Point prediction

> **160.7 / 162  =  99.2%**
> **Standard deviation 0.65 fields.**

### Distribution of possible outcomes

Since only two fields can move, the outcome is one of exactly four:

| Score | Requires | Probability |
|---|---|---|
| 162 | both correct | 0.25 x 0.40 = **10%** |
| 161 | exactly one wrong | 0.75(0.40) + 0.25(0.60) = **45%** |
| 160 | both wrong | 0.75 x 0.60 = **45%** |
| anything else | — | **0%** under this model |

**Most likely: 160 or 161, together 90%.**

### Per-document predictions

- **e16** — `wattage_w` returns **200**, ground truth 185. Wrong. 75% likely.
- **e14** — `model_number` returns **`AU-SOL-RS-12-30`** (OCR normalised),
  ground truth `AU-SOL-RS-l2-3O`. Wrong. 60% likely.
- **All 16 other documents — 9/9.**

---

## What would falsify this

Stated in advance, in order of how much each would matter.

### 1. A third document fails — MOST IMPORTANT

If any document other than e14 or e16 scores below 9/9, the claim behind
`docs/variance.svg` is wrong. That figure asserts that instability is confined
to fields requiring domain judgement, on the basis of two documents. A failure
elsewhere means variance is spread more widely than two documents could reveal,
and the figure overstates its case.

**Response if it happens:** weaken the claim in the figure and the README to
what two documents can actually support, and measure the failing document
before saying anything further about it. Do not delete the finding; narrow it.

### 2. Score below 159

Outside the range this model permits. Would mean either more unstable fields
than identified, or something changed that is not variance — a silent model
update, a schema or prompt change I have not accounted for, or a quota failure
mid-run.

**Response:** check `model` in `requests.jsonl` across the run boundary before
concluding anything about quality.

### 3. Score of 162

Permitted (10%) and not falsifying. But it must **not** be reported as
"the system scores 162/162". Under this model that is the lucky tail, and
reporting it without the distribution would be the exact dishonesty this file
exists to prevent.

### 4. A hard failure (no valid output)

Most likely cause is the daily quota: 18 documents against a 20-request limit
leaves room for two retries. `evaluate.py` now appends `-INCOMPLETE` to the
results filename in that case, so the run cannot be mistaken for a baseline.

**Response:** re-run tomorrow on a fresh quota. Do not report a partial run.

---

## What this run is NOT

- **Not a version comparison.** The measured noise floor is 1 field. v0 scored
  161/162 in a single run; a difference of one field against this baseline is
  indistinguishable from noise, and no claim about the footnote rule's effect
  on aggregate accuracy will be drawn from it.
- **Not evidence about real datasheets.** All 18 documents are synthetic.
- **Not a replacement for variance measurement.** It is one sample. It tests
  the model built from the variance runs; it does not add to them.

---

## What this run IS for

1. **Testing the variance model.** The prediction above either holds or does not.
2. **Restoring the destroyed baseline.** `results/v2.jsonl` was overwritten on
   Day 18 by a `--only e16` run.
3. **Producing the per-document failure map.** `results/failures-v2.json` is
   what the README and the case study are written from. The aggregate number is
   the least interesting output of this run.

---

## Recorded state at time of writing

| | |
|---|---|
| Date | Day 19 |
| Model | `gemini-3.6-flash` |
| Prompt version | v2 (domain rules + footnote precedence) |
| Documents | 18 |
| Judgements | 162 |
| Requests budgeted | 18 of 20 |
| Spend to date | $0.00 |
| Measured noise floor | 1 field per document, n=2 documents |

**Result to be appended below this line after the run, whatever it says.**

---

## RESULT

**Run completed. 18 documents, 18 requests, no hard failures.
`results/v2.jsonl` written with `is_baseline: true`.**

### Score

> **161 / 162  =  99.4%**
> 17 of 18 documents fully correct.

Predicted 160.7 ± 0.7. Observed 161 — the modal outcome, 45% likely, and
0.5 standard deviations from the point prediction.

| Outcome | Predicted probability | Occurred |
|---|---|---|
| 162 | 10% | |
| **161** | **45%** | **yes** |
| 160 | 45% | |
| anything else | 0% | |

### Per-document predictions

| Prediction | Outcome |
|---|---|
| `e16` `wattage_w` returns `200`, wrong — 75% likely | **Correct. Returned `200.0`, expected `185`** |
| `e14` `model_number` returns the OCR-normalised form, wrong — 60% likely | Wrong prediction. Returned the verbatim form and scored 9/9 — the 40% branch |
| All 16 other documents 9/9 | **Correct. All 16 clean** |

### Falsification conditions — none triggered

1. **A third document fails.** Did not happen. The only mismatch in 162
   judgements was `e16` `wattage_w`. The claim behind `docs/variance.svg` —
   that instability is confined to fields requiring domain judgement — survives
   a test that could have broken it.
2. **Score below 159.** Did not happen.
3. **Score of 162.** Did not happen, so the reporting hazard did not arise.
4. **Hard failure / incomplete run.** Did not happen. 18 requests, no retries
   needed, quota not exhausted.

### What the model got right, and what that is worth

The variance model built on Day 18 predicted the score of an unseen run, named
the failing field and its value in advance, and its falsification condition held.

It should not be over-read. The score has four possible values under this model
and two of them carry 90% of the probability, so a correct prediction is not a
strong test on its own. **The load-bearing result is falsification condition 1:**
sixteen documents that had one observation each were predicted stable, and all
sixteen came back 9/9. That is the part that could have gone wrong and did not.

### Incidental finding — the latency question is answered

| | Median latency |
|---|---|
| Day 18 variance runs (n=10) | 72,595 ms |
| Day 19 baseline runs (n=18) | **19,838 ms** |

Same model, same documents, same code, 3.7x faster. Day 18's latencies — up to
222 s on a 467-token request, with one attempt and no rate-limit message — were
throttling absorbed silently inside the SDK, not model slowness. That confirms
the hypothesis recorded on Day 6 and again on Day 18, and it means published
latency figures must state when they were collected.

### Cost

| | |
|---|---|
| Full 18-document run | $0.008367 at list price |
| Per document | **$0.000465** |
| Actually paid | **$0.00** — free tier |
