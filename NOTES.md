# NOTES

Working log — what I built, what broke, and what each failure taught me.
Not a diary. This is the raw material for the README case study and the failure taxonomy later in the project.

---

## DAY 1 — First LLM API call

**Date:** 11 August 2026
**Provider:** Google AI Studio (Gemini), free tier
**Model:** `gemini-3.6-flash`

### What I built

`extract.py` — takes a deliberately messy email (forwarded thread, informal tone, ambiguous and contradictory dates) and asks the model to identify the sender's intent and any dates mentioned.

Design decisions made on day one, deliberately:

- **API key in `.env`, never in code.** The key is read via `os.environ` after `load_dotenv()`. `.env` is gitignored and has never been committed.
- **Model name in a single variable.** `MODEL = "gemini-3.6-flash"` at the top rather than hardcoded inside the API call. This paid off within the hour — see the deprecation error below.
- **Email held as a variable, not inlined into the prompt string.** Keeps the input separate from the instruction, which matters once inputs come from a file or a request body.

### Errors hit, and what each one meant

**1. `.gitignore` written after `git add .` — staged `.env` and ~60,000 files from `.venv/`**

The key realisation: **`.gitignore` only filters untracked files.** Once something is staged, adding a rule does nothing. The index has to be cleared first (`git rm -r --cached .`), or the repo rebuilt.

Caught it at `git status` before committing, so nothing left the machine. This is the entire reason the check exists — staged is not committed.

Also learned: PowerShell's `Out-File -Encoding utf8` writes a byte-order mark that silently breaks the first line of a `.gitignore`. Use `-Encoding ascii`. And `git check-ignore -v <file>` tells you exactly which rule is ignoring something — the fastest way to prove a `.gitignore` is actually being read.

**2. `import os, from dotenv import load_dotenv, from google import genai` — `SyntaxError`**

Imports can't be chained with commas. Three statements, three lines. Python halts at the syntax error, so nothing below it runs.

**3. The email string wasn't assigned to anything**

I had a bare `"""..."""` sitting in the file. Python evaluates it and discards it. Without `EMAIL = ` in front, there is no variable — just a string that goes nowhere.

**4. f-string with no placeholder**

`prompt = f"What is the sender's intent...?"` — the `f` prefix does nothing without `{}` braces. Needed `{EMAIL}` to actually pull the email into the prompt. Without it I'd have been asking the model about an email it never received.

**5. `NameError: name 'MODEL' is not defined`**

I'd left a copied block from the quickstart near the top of the file that referenced `MODEL` and `prompt` before either existed. Python runs top to bottom — a variable defined on line 17 cannot be used on line 12.

Root cause was pasting two quickstart examples without reading them, then not recognising that they already contained the answer to what I was stuck on.

**6. `Model 'MODEL' not found` — 404 from the API**

Written as `model="MODEL"` with quotes. Quotes make it the literal five-character string; without quotes it's the variable holding `"gemini-3.6-flash"`. The API dutifully looked for a model named MODEL.

Notable: this error meant authentication and networking were already working. The request reached Google and came back with a real response. Errors that get further into the stack are progress.

**7. `models/gemini-2.5-flash is no longer available to new users`**

Model deprecation. Fixed by changing one line, because the model name was a variable rather than buried in the call. Concrete payoff for a decision made an hour earlier.

Lesson: live documentation beats secondhand sources on anything version-specific. The quickstart had the current model name; the article I'd been working from did not.

### What I actually learned

- **Read the last line of the traceback first.** Every error tonight said plainly what was wrong: `SyntaxError`, `NameError: name 'MODEL' is not defined`, `Model 'MODEL' not found`, `no longer available to new users`. None were cryptic. Most of the time lost was to not reading them closely.
- **Quoted string vs. unquoted variable** was behind a disproportionate share of the failures.
- **Execution order is file order.** Nothing can reference something defined below it.
- **Pasting code you haven't read costs more time than writing it.** The two blocks I copied from the quickstart already answered the question I was stuck on for twenty minutes.
- **Configuration belongs in variables**, proven the same day by a model deprecation.

### Time log

Substantially over the 3-hour budget. Breakdown, roughly:

| Block | Planned | Actual | Note |
|---|---|---|---|
| Setup, key, git | 45m | ~75m | Lost time to the `.gitignore` ordering problem |
| Writing `extract.py` | 60m | ~90m | Python syntax, not API concepts |
| Prompt experiments | 45m | 0m | **Deferred to Day 2** |
| Commit and push | 30m | ~15m | |

Honest read: the blocker was Python fundamentals — imports, string assignment, f-strings, variable scope — not anything about LLMs or APIs. Day 2 has been rescheduled to open with 45 minutes on fundamentals before Pydantic, since that's classes throughout.

### Deferred to Day 2

Prompt-behaviour experiments not yet run:

- [ ] `temperature=0.0` three times on the same input — are outputs identical?
- [ ] Empty string as input — error, refusal, or confident hallucination?
- [ ] **Garbage input (`asdkjfh 293847 ;;;;`) — does it invent an intent and dates?** ← the important one
- [ ] Prompt injection in the email body — does it follow the email or my instructions?

### Status

Day 1 complete: public repo, working script, API key handled correctly, secrets never committed.
