---
name: gridmatrix-retro
description: Turn recurring friction between Claude Code and Codex into written rules, by reviewing accumulated flags and audit findings and distilling the repeated ones into repo conventions. Use after roughly five merged tasks, when the same mistake has been flagged more than twice, when .agents/FLAGS.md is near its cap, or when the user asks why the two agents keep hitting the same problem. Do not use for a single incident, and do not use as a substitute for resolving an open flag.
---

# Retro

## Guard

Check that `.agents/FLAGS.md` exists. If not, say the repository has not adopted
the protocol and stop.

## What this is, and is not

Neither agent learns anything between sessions. Nothing here changes a model.
What accumulates is written rules, and what makes that work is that the output
lands in `AGENTS.md`, which both agents load every session without being asked.

So the only useful output of a retro is **a rule that would have prevented a
thing that already happened more than once**. Observations, summaries, and
encouragement are not output. If nothing recurred, the correct retro is "nothing
recurred," and you stop.

## 1. Gather

    git log --oneline -60
    git log --diff-filter=M --format='%h %s' -- .agents/REVIEW.md | head -30

Read `.agents/FLAGS.md` in full, `.agents/DECISIONS.md`, and the Conventions
section of `AGENTS.md`.

Past `REVIEW.md` contents live in git history because the file is cleared on
merge. `git show <commit>:.agents/REVIEW.md` recovers any of them.

## 2. Count, do not impress

Group what you found by cause, not by symptom. "Test failed" is a symptom;
"the builder assumed a fixture that only exists in CI" is a cause.

A pattern qualifies only at **three or more occurrences**. Two is a coincidence
and writing a rule from it costs both agents context forever in exchange for
nothing. Say how many times each pattern occurred, so the human can disagree
with your counting.

Look hardest at:

- The same S0 or S1 finding class recurring across different tasks. This is the
  strongest signal in the repo, because it means one agent reliably misses
  something the other reliably catches.
- `FRICTION` flags with a common cause.
- Any task that needed more than two rounds to resolve.
- Anything that had to be explained twice in handoffs.

## 3. Write at most one or two rules

Add them to the **Conventions** section of `AGENTS.md`, outside the managed
block markers, so updates preserve them.

The section is capped at ten one-line entries. When it is full you must merge
two existing rules or drop one that has not been violated recently. Appending
past the cap is not permitted: a conventions list that only grows stops being
read, and an unread rule is worse than an absent one because it looks like
coverage.

A good rule is specific, checkable, and describes behaviour rather than
attitude. "Verify fixtures exist locally before writing a test that depends on
them" is a rule. "Be more careful with tests" is not; it changes nothing about
what either agent does next.

If a pattern is better enforced than requested, say so and stop writing prose:
recommend a `PreToolUse` hook, a lint rule, or a CI check. A rule that a machine
can enforce should not be a sentence in a markdown file.

## 4. Update the calibration table

In `.agents/DECISIONS.md`, fill the rows for tasks completed since the last
retro: who built, who audited, what class of work, how many S0/S1 the audit
caught, what escaped, how many rounds to resolve.

If one platform has clearly caught more on a particular class of work across ten
or more tasks, propose changing the role assignment for that class and record it
as a numbered decision. Below ten tasks, say the sample is too small and leave
the alternating default alone. Do not rewrite the assignment rule off two data
points.

## 5. Prune FLAGS

Delete `resolved` flags whose pattern you just wrote into a rule, and leave one
line recording what they became. Keep every `open` and `disputed` flag. Keep
resolved flags that did not recur, since they may recur later.

## 6. Report

State: how many tasks since the last retro, which patterns recurred and how
often, which rules you wrote or merged, and what you deliberately did not write
because it happened only once or twice.

That last item matters. A retro that writes a rule for everything it saw is how
`AGENTS.md` becomes 400 lines of advice nobody follows.
