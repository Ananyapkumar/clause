# Failure Analysis

**System:** Clause - lighting datasheet extraction
**As of:** Day 15 · 12 documents · 108 hand-written judgements
**Current extraction accuracy:** 108/108 (100%) on whole-document extraction

---

## Summary

The extraction pipeline currently produces **zero field errors** on the eval set.
That is not the interesting part of this document, and taken alone it would be
misleading.

**A system with no observed failures has either solved the problem or has a test
set that cannot detect failure.** In this case, both are partly true, and the
distinction matters more than the score.

This document catalogues every failure mode observed across the project - in the
extraction, in the retrieval layer, and in the measurement apparatus itself.

---

## Category A - Extraction failures

**Observed on the current eval set: 0 of 108 fields.**

Failures observed earlier in development, all since resolved:

| Mode | Occurrences | Cause | Resolution |
|---|---|---|---|
| Out-of-range value accepted | 1 | Schema said "a number or nothing"; `1.8e+201` satisfied it | Domain-informed range constraints (`ge`/`le`) on six numeric fields |
| Wrong lifetime standard chosen | 1 | Domain rules removed in ablation; took L70/B50 over L80/B10 | Rule restored. This *is* the ablation result |
| Extraction degraded by citation requirement | 2 of 2 hard docs | Asking the model to extract *and* quote sources collapsed the primary task | Citations made opt-in, default off |

### Finding A1 - the schema accepted a physically impossible value

On one run the model returned `wattage_w = 1.8e+201` with every other field
null. Pydantic accepted it: the field was declared `Optional[float]`, and
`1.8e+201` is a float.

**Validation passed. Retry never fired. A completely wrong answer was returned as
a perfectly well-formed one.**

> This is the schema-versus-evaluation distinction demonstrated live.
> **Validation checks shape. Only ground truth catches values.**

**Fix:** range constraints derived from domain knowledge - a luminaire is not
1.8e+201 W, and CRI cannot physically exceed 100. Bounds err deliberately wide;
rejecting a legitimate datasheet is worse than accepting an absurd value.

**Caveat, stated honestly:** the event occurred once. Three clean runs afterwards
do not establish that the bounds *caused* the improvement, because the base rate
of that failure is unknown. What can be claimed is that the class of value is now
rejected and the retry has a chance to recover.

### Finding A2 - asking for extraction and justification degrades extraction

| | E02 (simple) | E01 (complex, 4 traps) |
|---|---|---|
| Fields correct | 9/9 | **1/9** |
| Citations | 9/9 verified, 0% hallucination | **0 returned** |
| `wattage_w` | correct | `1500.0000000000002` |

The `wattage_w` x10 error appeared in **all three** citation runs and in **none**
of the twelve runs before.

**The mechanism works. The trade is bad.** On simple input the cost is invisible;
on hard input it collapses the primary task.

**Fix:** citations opt-in, default off. **The correct architecture is two calls** -
one extracts, one cites, each doing a single job. Not implemented because it
doubles request count against a 20/day quota. It belongs in "what I would do
next."

---

## Category B - Retrieval failures

**These are the substantive failures.** Retrieval was built on Day 12 and
measured before any LLM call was made against it.

### Finding B1 - right document, wrong chunk

Query: *"system wattage of the track spot"*

Top hit: `e08::0` - the correct document, but the **header chunk**. It matched
the product title `AXIS TRACK SPOT - 24W`, not the specification line
`System power 24 W`. Ranks 2 and 3 were a different product entirely.

**Retrieving the right document is not retrieving the right chunk.** A system
measured at document level would score this as a success.

### Finding B2 - semantic search cannot distinguish lifetime standards

**The most important retrieval finding.**

Query: *"rated life hours"* - top hit `e10::4`:

```
Rated life L90/B10        35000 h
Product warranty          5 years (20000 h)
Ingress protection        IP40
```

**The chunk returned contains the two WRONG lifetime figures.** The correct
`Rated life L80/B10 60000 h` line sits in a different chunk and was not returned
at all.

To an embedding model, "L80/B10", "L90/B10" and "warranty" are near-identical
strings appearing in near-identical contexts. It has no way to know one is the
answer and the other two are traps.

**This is the same domain ambiguity the prompt-level rules were written for,
appearing one layer earlier - where prompt rules cannot reach it, because the
correct text never arrives in the prompt.**

**Implication:** retrieval needs domain awareness too. Metadata filtering,
field-specific queries with negative terms, or a reranker that knows L80/B10
outranks L90/B10 for this field. Prompt engineering alone is not a fix.

### Finding B3 - chunk boundaries separate label from value

Query: *"is it dimmable"*

- Rank 1: `e11::2` - ends immediately **before** the dimming line
- Rank 3: `e11::3` - **starts with** `Dimming Not dimmable`

The answer is at rank 3; rank 1 is the chunk that stops one line short. At k=1
this returns confidently wrong context.

Line-based chunking with overlap reduced this but did not eliminate it.

### Finding B4 - retrieval increased context rather than reducing it

**Measured across all 12 documents.**

| Setting | Documents where retrieval sent LESS | Overall context change |
|---|---|---|
| k=2 per field | **0 of 12** | **+24.7%** |
| k=1 per field | 3 of 12 | **+3.6%** |

Two causes:

1. **The corpus is too small for retrieval to filter anything.** Documents chunk
   into 2-6 pieces. Nine field queries at k=2 request 18 chunks from a pool of 5 -
   everything is selected. There is nothing to leave out.
2. **Chunk overlap is duplicated on reassembly.** Adjacent chunks share text by
   design; joining both reproduces the shared region twice. Visible directly in
   the output: `Downward (direct) 3150 lm` appears twice in the assembled context
   for e10.

**Decision: retrieval not adopted.** No accuracy measurement was run, and
deliberately so - retrieval's purpose is to send less text, it demonstrably sends
more, and spending 12 API requests would only confirm a conclusion already
established for free.

> **Retrieval is the wrong tool at this document size.** It becomes correct when
> documents exceed the context window, or when a corpus is large enough that most
> of it is irrelevant to any given query. The crossover was measured rather than
> assumed.

**The bug worth fixing regardless:** adjacent selected chunks should be merged
before assembly, not concatenated. That is a real defect in the retriever and it
would apply at any corpus size.

---

## Category C - Measurement failures

**Three consecutive sessions produced a wrong score because of a defect in the
answer key, not in the system being measured.**

| Session | Reported | Actual cause | Model was |
|---|---|---|---|
| Day 5 | 11.1% | A formatting example copied in as ground truth | **Correct on all 18 fields** |
| Day 6 | 92.6% | Two keys deleted from a file; read as `null` | **Correct on both** |
| Day 8 | 90.5% | Units inside values, booleans as strings | **Correct on all 6** |
| Day 11 | one field | L90/B10 recorded where the rule specifies L80/B10 | **Correct** |

### Finding C1 - a broken answer key produces an authoritative wrong number

This is the most dangerous failure in the project, because **nothing errors**. A
score appears, it looks precise, and it is fiction.

Had any of these been trusted, the following session would have been spent
"fixing" a pipeline that was already correct.

**Why they were caught cheaply:** the harness runs on a small set. The comparison
logic is identical at 3 documents or 300, so building it early surfaced each
defect while it cost minutes rather than an hour of labelling.

### Finding C2 - absent is not null

`truth.get(field)` returns `None` for a key that is **absent**. A forgotten field
therefore looked identical to a deliberate "the document does not state this."

- **Absent** means *I forgot to write this.*
- **Null** means *the document genuinely does not state it.*

Treating them alike silently converts an omission into an assertion - and marks
the model wrong for being right.

### Finding C3 - lenient comparison conceals convention violations

At one point every numeric value in a ground-truth file was a quoted string and
`dimmable` was `"TRUE"`. Six of seven passed anyway, because `float("150")`
succeeds and `bool("TRUE")` is truthy. Only `"4000 K"`, which cannot be coerced,
surfaced.

**A test that is too forgiving does not merely fail to catch problems - it
conceals them.** Six violations hid behind one visible failure.

### Finding C4 - a control that does not control

The first ablation removed domain rules from the prompt and produced **identical**
scores. That read as a null result: "the rules do not matter."

It was a broken experiment. The rules existed in **two** places - the prompt and
the `description` on every schema field, which is transmitted to the model on
every call. Only one copy was removed.

Identical scores are exactly what removing nothing predicts.

**Rebuilt to strip both.** Corrected result: removing the domain rules cost
exactly one field - `lifespan_hours` on E06, the document where a marketing
banner and an alternative lifetime standard both point away from the correct
figure. **The predicted field, in the predicted direction, for the predicted
reason.**

**The structural response, taken after the third occurrence:** the harness now
validates the ground truth the same way it validates model output - types,
required keys, unknown keys, placeholder detection. It refuses to score rather
than scoring against a defective key.

> **An evaluation score is only as trustworthy as the answer key behind it. The
> answer key needs its own validation.**

---

## Category D - The eval set itself

### Finding D1 - 100% means the instrument has no resolution

The current eval set produces 108/108. That is a problem, not an achievement.

- It cannot detect whether the next change helps or hurts
- It blocks any claim of documented improvement across versions
- It almost certainly does not represent production traffic

**Cause:** every document is fictional, written specifically to test known
failure modes, and the extraction rules were written *against those same known
modes.* The traps are ones the system was explicitly told about.

**What would fix it:** documents with failure modes not anticipated in advance.
Real-world documents (public manufacturer datasheets), OCR noise, multi-column
layouts, scanned tables, genuinely contradictory specifications, and cases where
domain experts would disagree.

**This is the highest-priority next action for the project.**

---

## Failure frequency, all categories

| Category | Distinct modes | Currently active | Resolved |
|---|---|---|---|
| A - Extraction | 3 | 0 | 3 |
| B - Retrieval | 4 | 4 | 0 (not adopted) |
| C - Measurement | 4 | 0 | 4 |
| D - Eval design | 1 | **1** | 0 |

**The one active, unresolved failure is that the eval set is too easy.**

---

## What I would do next, in priority order

1. **Harder eval cases.** Real public datasheets, OCR noise, layouts. Until the
   score drops below 100% there is nothing to improve and no way to measure a
   change.
2. **Fix chunk merging.** Adjacent selected chunks should merge, not concatenate.
   A real defect independent of corpus size.
3. **Two-call citation architecture.** Extraction and citation separately, so
   neither degrades the other. Doubles requests; needs quota headroom.
4. **Field-specific retrieval with domain awareness** - metadata filtering or a
   reranker that knows L80/B10 outranks L90/B10. Only worthwhile once documents
   are large enough for retrieval to be the right tool at all.
5. **Repeat runs for variance.** All current results are n=1 per condition.
   Direction and location of the ablation failure raise confidence, but a paired
   repeat would establish it properly. Costs 42 requests, or two days of quota.
