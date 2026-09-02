# Outreach templates

**Day 21.** Rewrite every one of these in your own words before sending. If it
sounds like a template it will be read as one, and the whole point is that it
does not read like the forty other messages that person got this week.

Three rules that matter more than the wording:

1. **Never ask for a job in the first message.** The ask is a conversation.
2. **Say one specific thing about them.** If you cannot, do not send it.
3. **Never send a link they have to earn.** Give the artifact freely.

---

## STAGE 1 — Connection request (300 characters, hard limit)

No ask. One specific reference. One line of proof. That is the whole job.

### 1A — CTO / Head of Engineering

> Hi [Name] — saw [company] is doing [specific thing]. I spend my time on
> evaluation for LLM systems: just finished a month measuring why my own
> extraction system's accuracy number was misleading me. Following your work.

### 1B — GenAI / ML tech lead

> Hi [Name] — your [post/talk/repo] on [specific] landed for me. I build eval
> harnesses for LLM extraction — most of my last month went on discovering my
> own measurement was broken three separate times. Would like to connect.

### 1C — Startup founder (non-technical or semi-technical)

> Hi [Name] — [company] looks like it lives or dies on [specific thing being
> right]. I work on the boring half of AI: measuring whether the output is
> actually correct, and how often it isn't. Would like to follow along.

### 1D — Someone whose post you actually replied to

> Hi [Name] — replied to your post on [topic] earlier. Short version of my
> view: [one clause of a real opinion]. Working on evaluation for LLM
> extraction systems at the moment. Connecting.

**1D converts best. Comment first, connect second.**

---

## STAGE 2 — First message after they accept

Send 2–4 days later. Never the same day — same-day messages read as automated.

Structure: **observation → what I did → artifact → no ask.**

### 2A — The default

> Thanks for connecting, [Name].
>
> Something I keep running into: teams ship an LLM feature, someone changes a
> prompt, and there is no way to say whether it got better. The number that
> exists is usually a single run.
>
> I spent the last month on that with my own system — lighting datasheet
> extraction, 18 documents, 162 hand-written judgements. The useful part was
> unpleasant: I measured the run-to-run variance and had to retract my own
> version comparison, because the difference I was reading sat inside the noise.
>
> Writeup and code here if it's useful to you: [github link]
>
> Not asking for anything — just the kind of thing I'd have wanted someone to
> send me six months ago.

### 2B — When they have a public LLM feature you can observe

> Thanks for connecting, [Name].
>
> I had a look at [feature]. One thing I'd be curious about: how do you tell
> whether a prompt change made it better? That's the question I've been living
> in — I built an eval harness for a document extraction system and the harness
> turned out to be wrong before the model was, three times.
>
> [github link] if you want the details. The interesting bit is the two
> components I built and then deleted because the measurement said they weren't
> earning their cost.

### 2C — Domain-adjacent (construction, manufacturing, industrial, spec data)

> Thanks for connecting, [Name].
>
> I came at AI from the lighting industry — product datasheets, specification
> data. What surprised me is that the hard part isn't the model, it's that a
> datasheet prints three numbers that could all plausibly be "the wattage", and
> only one is right. That's domain knowledge, not parsing.
>
> Built a system around exactly that: [github link]
>
> If you're dealing with anything similar — spec sheets, product data, technical
> PDFs — I'd be interested in how you're handling it.

---

## STAGE 3 — The ask

Only after a reply, or after two value-first messages with no reply. **Small,
scoped, low-risk, time-boxed.** The ask is not "hire me" — it is "let me do one
concrete thing".

### 3A — The eval offer (strongest, use this by default)

> [Name] — a concrete offer, take it or leave it.
>
> Pick one LLM feature you ship. I'll build you an evaluation harness for it in
> a week: 20–30 real cases with hand-written expected outputs, per-field
> scoring, and a number you can run on every prompt change. Free.
>
> Two things I'd want in return: 20 real examples, and 30 minutes to understand
> what "correct" means for your domain — that second part is where these
> normally go wrong.
>
> If it's useful we talk about doing more. If it isn't, you keep the harness.

### 3B — The audit offer (lower commitment, good for busy CTOs)

> [Name] — would it be useful if I spent two hours on [feature] and sent you
> what I find? Specifically: where it fails, how you'd measure it, and what I'd
> instrument first.
>
> No charge, no obligation, no follow-up sequence. I'm doing this to build a
> track record on real systems rather than my own synthetic data, and I'd rather
> be judged on the two hours than on my CV.

### 3C — The direct problem-hunt

> [Name] — direct question. Is there something on your list that's been sitting
> there for months because it's LLM work nobody has time for? Evaluation,
> extraction, a workflow that's still manual, a prompt nobody trusts?
>
> I'm looking for one real problem to work on. I'd do the first one free to
> show you what working with me is like.

### 3D — Contract, once there is proof

> [Name] — following on. Given [thing I did / what we discussed], would it make
> sense to scope this as a short contract? I'd suggest [2–4 weeks], fixed scope,
> and I'd want the first milestone to be something you can judge in week one.
>
> Happy to work to whatever rate is normal for you — I care more about the
> reference than the number right now, and I'd rather say that than pretend
> otherwise.

---

## STAGE 4 — Follow-up after silence

**One follow-up. Then stop.** A second follow-up costs you the contact.

Send 7–10 days later, and add something new — never "just bumping this".

> [Name] — one more and then I'll leave it.
>
> Since I wrote, I [specific new thing: measured X / published Y / found Z].
> [One line on what it showed.]
>
> Still happy to do the [audit / harness] if it's useful. Either way, no reply
> needed.

---

## STAGE 5 — When they say yes

Do not celebrate and go quiet. Reply within an hour with structure.

> Great. To make this concrete:
>
> **What I'd need from you:** [20 examples / access to X / 30 minutes]
> **What you'd get:** [the harness / the audit doc], by [specific date]
> **What I'd want to know first:** three questions below — the answers change
> what I build.
>
> 1. What does "wrong" cost you? A wrong [output] that reaches a customer —
>    what actually happens?
> 2. Who currently decides whether an output is correct, and how?
> 3. If you could only measure one thing about this feature, what would it be?
>
> Happy to do the 30 minutes on a call or in writing, whichever is less
> disruptive.

---

## The diagnostic questions

For calls, DMs, comment threads — anywhere. These surface a problem you can
solve, and asking them well is itself the demonstration.

**Measurement**
1. How do you know your LLM feature is working right now?
2. How would you find out if it got worse?
3. Who wrote the expected outputs you test against?
4. When you change a prompt, what tells you it helped?
5. How many times do you run an eval before you believe the result?

**Failure**
6. What is the failure your users actually complain about?
7. What does it cost you when the output is wrong?
8. Is there a failure you know about and have not fixed? Why not?

**Cost and scale**
9. What does one request cost you, and who watches that number?
10. What breaks first if volume goes up 10x?

**Domain**
11. Who on the team knows what "correct" means for this data?
12. Is that written down anywhere?

**Question 12 is the one that opens doors.** The answer is almost always no,
and the gap between "someone knows" and "it is written down" is precisely the
work.

---

## What NOT to send

| Don't | Why |
|---|---|
| "I'm passionate about AI" | Everyone is. It carries no information |
| "Looking for opportunities in AI/ML" | Reads as unemployed, not as useful |
| "I'd love to pick your brain" | An ask disguised as flattery. Costs them, gives nothing |
| "I'm a quick learner" | The claim of someone with nothing to point at. You have things to point at |
| A CV attachment in message one | Asks for effort before you have earned any |
| Anything over 120 words in message one | It will not be read |
| The same message to 40 people | Visible instantly. One specific line per person or don't send |

---

## Volume and realistic expectations

Be unsentimental about the arithmetic.

| Stage | Realistic rate |
|---|---|
| Connection requests accepted | 30–50% with a specific reason; 10–20% generic |
| Reply to first message | 10–20% |
| Reply to a scoped free offer | 20–40% **of those who replied** |
| Converts to real work | a handful, from ~100 contacts |

**So: 10 well-researched contacts per day, five days a week.** That is roughly
50 a week, 400 by Day 100. Ten minutes each — twenty per person is better than
forty at half the quality.

**Track everything.** `outreach/tracker.csv` — name, company, role, date,
stage, what you referenced, reply, next action. Without it you will
double-message people, which is the one unrecoverable error here.
