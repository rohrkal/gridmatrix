---
name: gridmatrix-audit
description: Adversarially review a change built by the other AI agent (Claude Code or Codex) against its written spec, and record findings by severity. Use when asked to audit, review, or check another agent's work, when picking up a task whose status is auditing, or before merging a task branch in a repository using the two-agent protocol. Do not use to review your own work from this same session, and do not use as a general code-review helper in repositories without an .agents/ directory.
---

# Adversarial audit

## Guard

Check that `.agents/TASKS.md` exists. If not, say the repository has not
adopted the protocol and stop.

Check who built the change under review. **If you built it in this session,
stop.** Self-audit produces agreement, not review. Say that a different agent
must audit it, and end.

## Ordering is the whole method

Follow this order. Do not skip ahead.

1. Read the task spec and acceptance criteria in `.agents/TASKS.md`.
2. Run `git diff main...HEAD` (substitute the real base branch) and read the
   diff.
3. Form your findings from those two sources alone.
4. **Only now** read `.agents/HANDOFF.md`, and revise your findings.

Reading the builder's rationale first anchors you to their framing and converts
the review into agreement. That single ordering error is how this protocol
degrades into theatre.

## Checks

- Re-run every gate in the **Gates** section of `AGENTS.md` yourself. Do not
  trust output the builder pasted. Reproducing it is the entire reason a
  second agent exists.
- Anything implemented but not specified is a finding.
- Anything specified but not implemented is a finding.
- Look specifically at: unhandled error paths, boundary and empty values,
  concurrency, silent failures, resource leaks, and tests that assert nothing.
- Construct at least one input intended to break the change. Report the attempt
  whether or not it succeeded.

## Severity

| Sev | Meaning                                       | Blocks merge |
| --- | --------------------------------------------- | ------------ |
| S0  | Incorrect, unsafe, or destroys data            | Yes          |
| S1  | Violates the spec or a stated contract         | Yes          |
| S2  | Maintainability, missing test, unclear naming  | No           |
| S3  | Nit, style, preference                         | No           |

## Output

Write to `.agents/REVIEW.md` using the structure already in that file. Every
finding needs a severity, a `file:line`, and a concrete reproduction or a
specific reason it is wrong.

Fill both closing sections:

- **What I verified**, with the commands you actually ran.
- **What I could NOT verify**, and why. This must not be empty. An audit with
  nothing in it is almost certainly a rubber stamp.

Then give a verdict: `blocked (S0/S1 open)`, `pass with S2/S3 noted`, or `pass`.

## Recurring findings

If a finding is one you have raised on a previous task, say so in the finding
and raise a `FRICTION` flag in `.agents/FLAGS.md` naming the pattern. A defect
that keeps returning is a missing rule, not a careless builder, and
`gridmatrix-retro` needs the count to justify writing that rule.

## Hard rule

**You do not fix anything.** Report only. If the fix is a single obvious
character, it is still a finding, not an edit. Fixing collapses the separation
that makes the audit worth running.

If you and the builder have already disagreed twice on the same point, stop.
Write both positions into `.agents/DECISIONS.md` with status `open` and escalate
to the human.
