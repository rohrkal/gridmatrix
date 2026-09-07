---
name: gridmatrix-handoff
description: Write the handoff baton file that passes work from this AI agent to the other one (Claude Code or Codex) in a repository using the two-agent protocol. Use when ending a work session, pausing a task, handing off for review, or when the user says they are done for now or switching tools. Do not use in repositories without an .agents/ directory, and do not use as a general changelog or commit-message writer.
---

# Handoff

## Guard

Check that `.agents/TASKS.md` exists. If not, say the repository has not
adopted the protocol and stop.

## Gather

    git status --short
    git log --oneline main..HEAD
    git diff --stat main...HEAD

## Write

Overwrite `.agents/HANDOFF.md`. Overwrite, do not append. It is the current edge
of the work, not a diary. Keep it under 100 lines.

Use the section structure already in the file. Two sections carry the weight:

**Section 2, "What I did NOT do."** Every in-scope thing left undone, every code
path you did not exercise, every test you skipped or stubbed. The next agent has
no memory of this session and will assume coverage that does not exist. Write it
even when it makes the session look incomplete. Omission here is the most
expensive failure in this protocol.

**Section 3, "Evidence."** Real command output, pasted. Not a summary of it.
Label every claim as one of:

- verified: you ran it and observed the result
- inferred: you reasoned it from code you read
- assumed: you do not know

"Tests pass" with nothing pasted is an assumption, not a result. Never present
one class as another.

## Flags

Before you write the handoff, deal with `.agents/FLAGS.md`:

- Anything you noticed about the other agent's work this session goes in as a
  typed flag. Ending a session with an unlogged observation loses it: the next
  agent reads files, not your replies.
- Any flag addressed to you that you fixed becomes `resolved` with what you did.
- Any flag you disagree with becomes `disputed` with your reason, which sends it
  to the human instead of blocking the other agent indefinitely.

Then record in the handoff, explicitly, which flags you raised and which you
answered. "None" is a valid answer and must be written rather than omitted.

## Then

- Update `.agents/STATE.md` **only if** the objective, constraints, or risks
  actually moved. Rewriting it out of habit is how it rots into noise.
- Update your task's `status` in `.agents/TASKS.md`.
- If you finished or abandoned the task, release the claim by setting `owner`
  back to `-`.

## Close

State in one line who should pick this up next and in which role. Whoever built
the change does not audit it.
