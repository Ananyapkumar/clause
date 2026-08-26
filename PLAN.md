# PROJECT 1 — 30-DAY PLAN

**Live status document. Updated every day. This supersedes every earlier plan.**

**Project:** Clause — lighting product datasheet extraction
**Live:** https://clause-9kq9.onrender.com/docs
**Written:** 19 August 2026 · **Replaces:** the pre-rescope compliance-checker plan

---

## HARD CONSTRAINTS — these are not negotiable

| # | Constraint |
|---|---|
| 1 | **Total additional cost: $0.** No paid APIs, no paid hosting, no credits, no subscriptions beyond Claude. |
| 2 | **Finish in 30 project days.** Currently on Day 15. |
| 3 | **≤14 API requests per day.** Free tier is 20/day. |
| 4 | **No new tool introduced without stating its cost first** — even free ones. |
| 5 | **Beginner-friendly.** No Docker requirement, no cloud consoles, no complex setup. |
| 6 | **Ground truth written by hand, never by a model.** |

**Rules I follow, on myself:**
- One eval run per version. No repeat runs unless a result is genuinely surprising.
- Nothing added mid-day. If it isn't in that day's plan, it waits for the next version boundary.
- Every day opens with: *original plan said X · we're doing Y · because Z.*

---

## STATUS

```
DAYS COMPLETE   ###############...............   15 / 30
SPENT           $0.00
WEEK 1 GATE     9 / 9  PASSED
WEEK 2          COMPLETE
```

| Metric | Value |
|---|---|
| Baseline v0 | **108/108 fields (100%), 12 documents** |
| Ablation | 61/63 — one field, exactly where the removed rule applies |
| Cost per 7-doc run | $0.0033 (free tier — not charged) |
| Median latency | ~9.8 s |
| Eval set | 12 documents · 108 hand-written judgements |
| Commits | across 9 distinct days |

---

## WHY THIS PLAN DIFFERS FROM THE ORIGINAL

On Day 5 the project was rescoped, at your instruction, from a **contract
compliance checker** to a **lighting datasheet extractor**. That changed what
the artifacts are called, not what they do:

| Original plan | This project | Why |
|---|---|---|
| `SPEC.md` — 12–15 rules | `schema.py` — 9 fields + domain decisions | Datasheets have fields, not pass/fail rules |
| `data/raw/` — 30 contracts | `evals/documents/` — 7 datasheets | Fictional; real employer docs excluded |
| `data/gold.jsonl` | `evals/ground_truth/*.json` | One file per document is easier to hand-edit |
| `RuleVerdict` | `LightingDatasheet` | Same idea, different domain |
| `results/v0.jsonl` | `results/v0.jsonl` | Unchanged |

**One thing genuinely dropped and now restored:** the original included
`expected_span` and `char_offset` — citation checking. That is Day 10.

---

# ✅ DAYS 1–9 — COMPLETE

| Day | Delivered | Cost |
|---|---|---|
| **1** | Public repo, first API call, `.env` handling, secrets never committed | $0 |
| **2** | Pydantic schema, native structured output, retry ×3 on validation failure, 4 adversarial experiments | $0 |
| **3** | Hand-written tool-calling loop, 3 tools, parallel calls handled, no framework | $0 |
| **4** | FastAPI service, JSONL request logging, cost/latency analysis | $0 |
| **5** | **Rescoped to lighting datasheets.** 9-field schema with documented domain decisions. Evaluation harness built at 3 cases. | $0 |
| **6** | E01 hard case scored 9/9. Deployed to Render. Ground-truth validation hardened. | $0 |
| **7** | README case study, GitHub + LinkedIn repositioned, Week 1 review. **Gate 9/9.** | $0 |
| **8** | Range constraints after schema accepted `1.8e+201`. Eval set 3→7 documents. Ground-truth type validation. Rate-limit handling. | $0 |
| **9** | Ablation harness. First attempt invalid (rules leaked via schema descriptions) — rebuilt. Result: removing domain rules cost exactly `lifespan_hours` on E06. | $0 |

**Findings so far:** self-reported confidence tracks the schema not the truth ·
output is non-deterministic · latency is not driven by input length · the API is
stateless · thought signatures must be preserved · parallel tool calls happen ·
a broken answer key produces an authoritative wrong number · absent ≠ null ·
lenient comparison hides violations · prompt injection resisted (n=1) · free-tier
quota is 20/day and that shapes iteration speed.

---

# ✅ WEEK 2 · DAYS 10–15 — COMPLETE

| Day | Delivered | Requests | Cost |
|---|---|---|---|
| **10** | Citation verification built and measured. Degraded extraction on hard documents → made opt-in. | 6 | $0 |
| **11** | Eval set 7 → 12 documents, 108 hand-written judgements. **v0 = 100%.** | 12 | $0 |
| **12** | Chunking, embeddings, ChromaDB. Four retrieval failure modes documented, no LLM in the loop. | 0 | $0 |
| **13** | Retrieval measured: **increased context 24.7%**. Not adopted, on evidence. | 0 | $0 |
| **14** | Week 2 review. | 0 | $0 |
| **15** | `FAILURE_ANALYSIS.md` — 12 failure modes, 4 categories. | 0 | $0 |

**Week 2 total spend: $0.00. Requests used: 18.**

---

## SUPERSEDED PLAN FOR DAYS 10–14 (kept for the record)

### DAY 10 — Span citation and hallucination rate
**Cost: $0 · Requests: 7**

*Original plan said: `expected_span` + `char_offset` in gold data. We're doing exactly that, restored after the rescope dropped it.*

- Add `source_span` and `source_offset` to the schema
- Verify programmatically that each extracted value appears **verbatim** in the document
- Values that don't → flagged `unverified`
- Run the eval; record the hallucination rate

**Output:** a sentence like *"X% of extracted values were not verbatim-present in the source and are automatically flagged."*
**Why:** right now you know *whether* a value is right, not whether the model *read it or invented it.* This is a stronger portfolio feature than accuracy.

### DAY 11 — Grow the eval set to 12
**Cost: $0 · Requests: 12**

- 5 new datasheets (I generate, you write ground truth **by hand**)
- Mix: 2 baseline, 2 hard, 1 adversarial
- Re-run, publish the new baseline

### DAY 12 — Chunking, embeddings, local vector store
**Cost: $0 · Requests: 0**

- `pip install chromadb sentence-transformers` — **free, local, no Docker, no account, no key**
- Two chunking strategies; index all 12 documents
- Search CLI; 10 test queries; note where retrieval fails

### DAY 13 — Retrieval pipeline → v1
**Cost: $0 · Requests: 12**

- Retrieve relevant chunks instead of sending the whole document
- Run the eval → `v1`
- Compare v0 vs v1: accuracy, cost, latency. **Cost should drop sharply. Accuracy may drop — that is a finding.**

### DAY 14 — Week 2 review
**Cost: $0 · Requests: 0**

- Update README with v0/v1 and the hallucination rate
- Week 2 review in `NOTES.md`
- Commit, push

---

# WEEK 3 · DAYS 15–21 — DIAGNOSE, IMPROVE, HARDEN

### DAY 15 — Failure analysis
**$0 · 0 requests** — Read every failure. Categorise and count: *marketing figure taken over technical · LED load over system · module flux over luminaire · warranty over rated life · retrieval missed the chunk · my label was wrong.* Write `FAILURE_ANALYSIS.md`.

### DAY 16 — Fix the top failure → v2
**$0 · 12 requests** — Fix **one** category. Re-run. Record the delta. One change, one measurement.

### DAY 17 — Verification agent → v3
**$0 · 12 requests** — Extend the Day 3 tool loop: a second pass that checks whether the cited span supports the value, and re-reads if not. Measure the cost/accuracy tradeoff.

### DAY 18 — LangGraph port
**$0 (open source) · 12 requests** — Port the hand-written loop to a state machine. Confirm evals unchanged. Write down honestly what the framework gave you and what it cost.

### DAY 19 — Production robustness
**$0 · ~5 requests** — Retries with backoff (partly done), provider failover, timeouts. Chaos test: kill the network mid-run, feed a corrupt file, feed an empty file.

### DAY 20 — Observability
**$0 · ~5 requests** — Upgrade the existing JSONL logging: `run_id` threaded through, per-call trace reconstruction, a small dashboard script. **No Langfuse account needed** — your logs already hold the data.

### DAY 21 — Full regression + Week 3 review
**$0 · 12 requests** — Re-run v0→v3. Build the metrics chart. Week 3 review.

---

# WEEK 4 · DAYS 22–30 — SHIP AND FACE THE MARKET

### DAY 22 — Redeploy
**$0 · 0 requests** — Update the Render deployment with the retrieval stack. Verify from your phone.

### DAY 23 — Demo interface
**$0 · ~3 requests** — Streamlit or Gradio: upload a datasheet, see extracted fields **with the source span highlighted**. Free tier hosting. 90-second screen recording.

### DAY 24 — README as case study, final
**$0 · 0 requests** — Metrics table above the fold, architecture diagram, schema decisions, evaluation methodology, results v0→v3, failure analysis, what I'd do next.

### DAY 25 — Technical write-up
**$0 · 0 requests** — ~1,200 words. *"I hand-wrote 63 judgements to find out whether my extractor actually worked — and the answer key was wrong three times."* Publish free on Substack or dev.to.

### DAY 26 — Positioning and launch
**$0 · 0 requests** — LinkedIn headline, About, Featured. Post the project leading with the failure analysis, not the launch.

### DAY 27 — Resume
**$0 · 0 requests** — One page. Project above employment history. Every bullet carries a number.

### DAY 28 — Target pipeline
**$0 · 0 requests** — 40 companies: remote-first, hiring AI engineers, hire internationally. Named contact for each. Draft 5 outreach messages.

### DAY 29 — Day 30 gate audit
**$0 · 0 requests** — Score honestly against the gate below. Write `RETROSPECTIVE.md`. Open your GitHub in incognito for five minutes and write down what a hiring manager would conclude.

### DAY 30 — First market contact
**$0 · 0 requests** — Send the 5 outreach messages. Apply to 3 roles. **Actually send them.**

---

# DAY 30 GATE

| # | Criterion | Status |
|---|---|---|
| 1 | Live, publicly accessible deployed system | ✅ |
| 2 | Hand-written tool-calling loop, explainable unaided | ✅ |
| 3 | Hand-written ground truth, 100+ judgements | ✅ 108 |
| 4 | Eval harness with per-field reporting | ✅ |
| 5 | Documented improvement across ≥3 versions | ⏳ v0 only |
| 6 | Written failure taxonomy with counts | ✅ `FAILURE_ANALYSIS.md` |
| 7 | Citation verification + stated hallucination rate | ⚠️ Built, measured, not adopted — documented |
| 8 | Agentic verification with measured cost/benefit | ⏳ Day 17 |
| 9 | Observability with real traces | ⏳ Day 20 |
| 10 | Docker + one-command startup | ✅ |
| 11 | README as case study | ✅ |
| 12 | Published technical write-up | ⏳ Day 25 |
| 13 | LinkedIn + resume repositioned | ⏳ partial |
| 14 | 40-company pipeline | ⏳ Day 28 |

**Currently 7 of 14**, plus one built-and-rejected-with-evidence. Six remaining, all scheduled, all free.

**Blocking item 5** (improvement across ≥3 versions): the eval set is at 100% and cannot detect improvement. **Harder eval cases are the next priority.**

---

# COST — ALL 30 DAYS

## Required: $0.00

| Item | Cost | Notes |
|---|---|---|
| Gemini API | $0 | Free tier, 20 requests/day |
| Render hosting | $0 | Free tier, sleeps when idle |
| GitHub | $0 | Public repos unlimited |
| ChromaDB, sentence-transformers | $0 | Local, open source, no account |
| LangGraph | $0 | Open source |
| Streamlit / Gradio | $0 | Free hosting tier |
| Substack / dev.to | $0 | Free publishing |
| Python, FastAPI, Pydantic, uvicorn | $0 | Open source |

## Optional, and all avoided

| Thing | Would cost | Free path taken instead |
|---|---|---|
| Gemini paid tier | ~$1–2/mo | Free tier + ≤14 requests/day |
| Langfuse | free tier exists | Own JSONL logging |
| Qdrant Cloud | free tier exists | ChromaDB locally |
| Render paid | $7/mo | Free tier |
| Custom domain | ~$12/yr | GitHub URL |
| Any course | varies | Not in the plan |

**Maximum realistic spend across the remaining 21 days: $0.00.**

---

# THE REQUEST BUDGET

Free tier: **20/day**. No day in this plan exceeds **12**.

| Days | Requests/day |
|---|---|
| 10, 11, 13, 16, 17, 18, 21 | 7–12 |
| 19, 20, 23 | 3–5 |
| 12, 14, 15, 22, 24–30 | 0 |

**If a run fails on quota:** wait for the reset. Do not switch models mid-project
(it invalidates every prior result) and do not enable billing.

---

# NOT DOING — and why

| | Why not |
|---|---|
| Repeat runs for statistical confidence | Research standard, not a portfolio requirement. n=1 with a stated caveat is honest and sufficient. |
| Switching model | Invalidates every result measured so far. |
| Enabling billing | Violates constraint 1. |
| Local Docker | Doesn't run on this machine. Render builds the image remotely. Not needed. |
| A second project | Depth is the signal. One project, done properly. |
| Any new framework beyond LangGraph | Scope discipline. |
| Real employer documents | IP boundary. Fictional documents only, permanently. |

---

# STANDING NOTES

- **Ground truth is written by hand.** Every document-generation prompt ends with *"Do not tell me what the extracted values are."*
- **E02 and E03 ground truth was assisted** (transcription only, verified) and cannot be cited as expert-written. E01 and E04–E07 are unassisted. All future cases unassisted.
- **No API keys on the work machine. No company data into any AI tool.**
- **Comparisons stay within one model.** Every results file records which model produced it.
- **Publish bad numbers.** A documented correction beats a clean first run.

---

*Updated at the end of every project day. If this file and reality disagree, this file is wrong — say so.*
