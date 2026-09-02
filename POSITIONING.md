# Positioning

**Day 20.** The sentence, the proof behind it, and the objections it has to survive.

---

## The problem with the obvious positioning

"AI Engineer, open to remote opportunities" competes with every bootcamp
graduate and every laid-off engineer retraining. It is a category with enormous
supply and no differentiation, and the only lever left inside it is price.

So the positioning cannot be a job title. It has to be a **problem I can prove
I solve**.

---

## The wedge

> **Most teams shipping LLM features cannot tell you whether last week's prompt
> change made things better or worse.**

This is true almost everywhere and it is not controversial. Teams ship a
feature, someone tweaks a prompt, someone else says it "feels better", and
nobody has a number. When quality degrades it is found by a customer.

It is a real problem, it is unglamorous, it is under-served, and it is exactly
what the last month of work demonstrates.

## The sentence

> **I build the measurement layer for LLM systems — the evaluation harness that
> tells you whether a change actually improved anything, and the domain rules
> that make the answer key correct in the first place.**

Second version, for a non-technical founder:

> **I work out whether your AI feature is actually right, and how often it
> isn't. Most teams are guessing.**

---

## Why this is credible from where I stand

Not "I am a senior AI engineer." That claim does not survive one follow-up
question. This one does:

| Claim | Evidence |
|---|---|
| I measure LLM systems properly | 18-document eval set, 162 hand-checked judgements, per-field reporting, ground-truth validation built into the harness |
| I find measurement errors, including my own | Four occasions the harness reported a failure and the answer key was wrong. Three drove structural fixes |
| I know what a result is worth | Measured a 1-field noise floor, then **retracted my own version-to-version comparison** because it sat inside it |
| I can predict my own system | Pre-registered a prediction in git, ran the baseline, prediction held. `PREDICTION.md` |
| I remove things that do not earn their cost | Citations, retrieval, and a verification pass — all built, measured, rejected, with the numbers recorded |
| I translate domain judgement into machine rules | System wattage vs LED load, L80/B10 vs warranty, luminaire vs module flux — decisions a generalist does not know exist |

**The last row is the moat.** Anyone can call a model with a schema. The
expensive, uncopyable part is knowing which of two plausible numbers on the page
is the right one — and that is what makes an answer key worth anything.

---

## What I am NOT claiming

Stated here so it is never claimed by accident.

- Not years of production experience. Twenty days of focused build.
- Not a system with real users. Deployed, reachable, test traffic only.
- Not tested on real documents. All 18 eval cases are synthetic.
- Not a distributed-systems or MLOps engineer.
- Not someone who has trained a model.

Every one of these is in the README. Volunteering them is the positioning, not
a weakness in it — the person who tells you what their number does not mean is
the person whose numbers you can use.

---

## The three objections, and the answers

**"You have no professional experience."**
> True. What I have is a system where I can show you the measurement, the
> failures, and the two components I removed because the numbers said to. Most
> people who have shipped LLM features for two years cannot show me any of
> those. I would rather be judged on that than on a date range.

**"Your project is synthetic data."**
> Yes, and the README says so in the limitations section. What transfers is not
> the accuracy number — it is the harness, the schema decisions, and the habit
> of finding out that my own measurement was broken. Give me twenty of your real
> documents and I will tell you where it breaks.

**"Why should we pay you rather than a senior engineer?"**
> You probably should pay a senior engineer, for senior engineering. What I am
> offering is narrower and cheaper: the evaluation layer your team keeps
> deferring because it is not a feature. It takes me days, not months, and after
> it exists your senior engineers can tell whether their changes work.

---

## Where this points

Not "AI Engineer, open to work". The ladder is:

```
free / cheap scoped work  ->  paid contract  ->  retainer or role
        (proof)                  (revenue)           (stability)
```

The first rung is the only one that matters right now, because it converts
"someone who built a portfolio project" into "someone who solved a problem for
a named company". Nothing else on a CV does that.
