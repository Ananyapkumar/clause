# LinkedIn profile

**Day 21.** The profile is where every message you send gets checked. It has one
job: make the person who clicks through think *"this person can actually do the
thing"* within about fifteen seconds.

Rewrite all of this in your own words. It has to sound like you, or the first
call will be a surprise to whoever took it.

---

## Headline (220 characters)

Not a job title. A problem.

**Option A — the wedge, most specific**

> I build the measurement layer for LLM systems — evaluation harnesses that tell
> you whether a prompt change actually improved anything | Lighting industry
> background | Open to contract work

**Option B — leads with the domain advantage**

> Lighting industry → AI engineering. I build extraction systems for technical
> documents and the evaluation that proves they work | Python, LLM APIs,
> RAG, LangGraph

**Option C — shortest, highest confidence**

> I find out whether AI systems are actually right, and how often they aren't.

**Use A.** C is memorable but says nothing about what you can be hired to do, and
B buries the differentiator behind a career-change story.

**Do not use:** "Aspiring AI Engineer", "AI Enthusiast", "Passionate about AI",
"Seeking opportunities". Every one of them announces that you have nothing to
point at — and you do.

---

## About section

First two lines are all that shows before "see more". They carry the whole load.

> Most teams shipping LLM features can't tell you whether last week's prompt
> change made things better or worse. I build the measurement that answers that.
>
> I came to AI engineering from the lighting industry, where I spent years
> reading product datasheets. That turned out to matter more than I expected.
> A datasheet prints three numbers that could all plausibly be "the wattage" —
> system power, LED load, and an efficacy figure that looks like both. Only one
> is right, and picking wrong means an undersized circuit. That is domain
> judgement, not parsing, and it is the part an extraction system cannot get
> right on its own.
>
> So I built one that does. Nine fields, an 18-document evaluation set with
> hand-written ground truth, and per-field scoring. It runs at 161 of 162 field
> judgements.
>
> The number is the least interesting part. What I actually learned:
>
> • I measured the run-to-run variance and found a noise floor of one field per
>   document — which meant retracting my own version-to-version comparison,
>   because the difference I had been reading sat inside the noise.
> • Three separate times the evaluation reported a failure and the answer key
>   was wrong, not the model. Each one made the harness stricter.
> • I built three components — source citations, a retrieval pipeline, and a
>   second-pass verifier — measured each against the eval set, and removed all
>   three. The verifier turned out to return whatever value it was handed, in
>   both directions. Two API requests to find out.
>
> I write down what my numbers do not mean, because a number without that is
> just a decoration.
>
> Currently looking for contract work on LLM systems — particularly evaluation,
> extraction, and anywhere domain knowledge has to be encoded before a model can
> be trusted with it.
>
> Code, measurements and the things that failed: github.com/Ananyapkumar/clause

**Why this works:** it opens with a problem the reader recognises, earns the
domain claim with a concrete example, gives a number, and then spends most of
its length on what went wrong. The three bullets are the differentiator — almost
nobody writes those, and they are the reason a technical reader keeps reading.

---

## Featured section

Three items, in this order. This is the part most people leave empty and it is
the highest-value real estate on the page.

1. **The repository** — title it *"Lighting datasheet extraction — 161/162, with
   the measurement behind it"*, not "clause".
2. **The variance figure** (`docs/variance.svg`) — upload as an image. It is the
   single most unusual thing you have and it reads in three seconds.
3. **`PREDICTION.md`** — titled *"I predicted my system's score before running
   it. Here's the result."* Link straight to the file.

---

## Experience entry

Give the project a real entry. Dates honest, framing professional.

**Title:** AI Engineer — independent project
**Dates:** [month] 2026 – present

> Built and deployed a document extraction system for lighting product
> datasheets: nine validated fields, structured outputs with retry-on-validation-
> failure, FastAPI service on Render.
>
> The substance is the evaluation. 18-document eval set, 162 hand-written field
> judgements, per-field scoring, and ground-truth validation built into the
> harness after three separate occasions where the answer key was wrong and the
> model was right.
>
> Measured a run-to-run noise floor of 1 field per document and used it to
> retract a version comparison that sat inside the noise. Pre-registered a score
> prediction in version control before the baseline run; it held.
>
> Built and removed three components on the evidence — citations, retrieval, and
> a verification pass — each with the measurement recorded rather than deleted.
>
> Python · Pydantic · FastAPI · LLM APIs · LangGraph · ChromaDB · Render

Keep your lighting role above it, with a line about specification and product
data. **Do not hide it.** It is the reason you are worth talking to.

---

## Posting — three per week from Day 22

Posts do more than messages, because they reach people who never accepted your
connection request. Three that are already written, in your notes:

1. **"My eval said 11% and the model was right."** The contaminated answer key.
   Every engineer who has built an eval recognises this and almost nobody
   admits it.
2. **"I built a verification agent. It agreed with everything."** Shown its own
   preferred answer it kept it; shown a value against its prior it kept that
   too. Two requests to kill a feature.
3. **"My accuracy number was a single sample and I didn't know."** The noise
   floor, and retracting your own comparison.

Structure each the same way: **the mistake → the measurement → what you changed.**
Two hundred words. No hashtag pile. Post 1 first — it is the most relatable.

---

## What to fix today

- [ ] Headline (option A)
- [ ] About section
- [ ] Featured: repo, figure, PREDICTION.md
- [ ] Experience entry for the project
- [ ] Photo and banner — plain and professional is enough; absent is not
- [ ] Turn on "Open to work" for **contract/freelance**, recruiters-only
      visibility if your current employer is a concern
