<!-- gridmatrix templates. Each section below is written to the path in its
     marker. Edit here to change your house defaults for every future repo. -->

>>>> FILE: AGENTS.head
# AGENTS.md

Canonical instruction set for every AI agent in this repository. Codex reads it
natively; Claude Code reads it through `CLAUDE.md`. Shared rules live here and
tool-specific files hold only tool-specific mechanics, because duplicating a
rule across both guarantees drift.

Keep this under 200 lines: longer instruction files lose adherence, which leaves
rules present and ignored.

## 1. Project facts

<!-- Any line you did not verify must end with (unverified). -->

- Purpose: PLACEHOLDER
- Language / runtime: PLACEHOLDER
- Package manager: PLACEHOLDER
- Entry point: PLACEHOLDER
- Deploy target: PLACEHOLDER

## 2. Verified commands

A command belongs here only after an agent ran it here and saw it succeed. Never
infer one from the file tree: blank makes the next agent check, wrong makes it
confidently do nothing useful and report success.

| Purpose   | Command     | Last verified (date + agent) |
| --------- | ----------- | ---------------------------- |
| Install   | PLACEHOLDER |                              |
| Build     | PLACEHOLDER |                              |
| Test      | PLACEHOLDER |                              |
| Lint      | PLACEHOLDER |                              |
| Typecheck | PLACEHOLDER |                              |
| Run local | PLACEHOLDER |                              |

## 3. Conventions

<!-- Yours to write; the installer never touches anything outside the managed
     block below. gridmatrix-retro also writes distilled rules here.
     Hard cap 10 entries, one line each. When full, retro must merge or drop a
     rule rather than append: a conventions list that only grows stops being
     read. Long conventions go in docs/ with a one-line pointer here. -->

- PLACEHOLDER

>>>> FILE: AGENTS.block
<!-- gridmatrix:begin -- managed block, replaced on update. Write repo-specific
     rules OUTSIDE these markers; everything outside is preserved. -->

## Two-agent coordination

Claude Code and Codex both work this repository. They cannot talk to each other:
no channel, no shared memory, no shared context, no memory between sessions. All
coordination is write-then-read through git and the filesystem. If you catch
yourself writing "I'll let the other agent know," stop. You cannot. Write it in
a file.

### Session start, before any code

You already have this file. Also read `.agents/STATE.md`, `.agents/HANDOFF.md`,
`.agents/TASKS.md`, and `.agents/FLAGS.md`, in that order. Then run `git log --oneline -15` and
`git status --short` and reconcile against STATE. Git is ground truth; if STATE
disagrees it is stale, so fix it and say so.

### Single writer

One task, one owner, one branch, one working tree. Never run both agents against
the same working directory at once; they clobber each other silently and the
filesystem gives no warning. Use `git worktree add` for real parallelism.

Git is the lock. To claim a task, set `owner` and `status` in `.agents/TASKS.md`
and commit **that file alone** as `chore(agents): claim T-XXX`. A rejected push
means someone else claimed it first: pull and pick another task. The claim commit
is deliberately tiny so the race is visible instead of silent.

### Roles

BUILDER writes the change. AUDITOR tries to break it with fresh context and does
not fix. **Whoever built a change does not audit it.** Roles attach to a task,
not a platform; alternate by task ID.

### Skills available

`gridmatrix-session-start` loads state, `gridmatrix-handoff` writes the baton,
`gridmatrix-audit` reviews the other agent's change, `gridmatrix-retro` distils
recurring friction into rules, `gridmatrix-adopt` sets up a repo. Invoke by name
for certainty; either tool may also select one by description.

### Task lifecycle

    SPEC -> CLAIM -> BUILD -> VERIFY -> AUDIT -> RESOLVE -> MERGE

No code before acceptance criteria exist in the task entry, checkable by someone
who was not in the conversation. "Handles errors properly" fails that test;
"returns 422 with `{code}` on malformed input, covered by a test" passes. The
spec is what stops two agents building to different readings of one sentence.

At RESOLVE every finding gets a disposition: fixed, waived with reason, or
deferred to a new task ID. Nothing closes silently.

### Gates

No task is done until all of these pass on the task branch:

1. Build succeeds.
2. The **full** test suite passes. Not a subset. Not "the tests I wrote."
3. Lint and typecheck pass with zero new findings.
4. The diff contains nothing outside the task's declared scope.
5. An audit by the other platform is in `.agents/REVIEW.md` with no unresolved
   S0 or S1 findings.
6. No flag in `.agents/FLAGS.md` addressed to you is still `open`.

Gates are objective and agent opinion is advisory. Never mark work complete on
the basis of reasoning alone.

Severity, used in gates 5 and 6 and in `.agents/REVIEW.md`. **S0** incorrect,
unsafe, or destroys data. **S1** violates the spec or a stated contract. Both
block merge. **S2** maintainability or missing test, **S3** nit: neither blocks.

### Evidence

Label every claim: **verified** (you ran it and saw the result), **inferred**
(reasoned from code you read), or **assumed** (you do not know). Never present
one as another. "Tests pass" with no pasted output is an assumption.

For bugs the order is fixed: reproduce, show the failing output, fix, show the
passing output.

### When you notice something wrong

You will find problems outside your own task: a wrong handoff, a broken test the
other agent did not mention, a stale STATE, two agents in the same files. Say so
in `.agents/FLAGS.md`. Never fix another agent's work silently, and never leave
the observation in your reply only, where the other agent will never see it.

Append a typed flag:

- **COLLISION** you and the other agent are in the same branch, worktree, or
  files. Stop work and raise it before writing anything else.
- **DEFECT** completed work of the other agent's is wrong, found outside an
  audit. Include how to reproduce.
- **FRICTION** something cost you time that a written rule would have prevented.
  These are the raw material `gridmatrix-retro` distils into conventions, so
  they are worth logging even when nobody is at fault.

The bar is: would the other agent change what it does next if it knew? If not,
do not flag it. A flag file nobody trusts is worse than none.

Answer flags addressed to you before starting new work: set `status` to
`resolved` with what you did, or to `disputed` with why, which escalates to the
human instead of blocking forever.

### Change discipline

Minimal diff. Never rewrite working code the task did not ask you to change. No
opportunistic refactors: file them in the `.agents/TASKS.md` backlog. No new
dependencies without a `.agents/DECISIONS.md` entry. No reformatting of files
you are not otherwise editing, because format churn hides real changes from the
auditor.

### State files

`STATE.md` is the current picture, edited only when it changes. `TASKS.md` is
the queue and the lock. `HANDOFF.md` is overwritten each session. `REVIEW.md` is
cleared on merge. `DECISIONS.md` and `FLAGS.md` are append-only; `gridmatrix-retro`
prunes FLAGS. Caps in lines: STATE 120, TASKS 200, HANDOFF 100, REVIEW and FLAGS
150. Over cap means summarize and cut, not append. A state file nobody reads is
worse than none, because it looks like coordination while providing none.

### Stop and escalate

- The task cannot be done without going outside its declared scope.
- You and the other agent have disagreed twice on the same point. Cap it there,
  write both positions into `.agents/DECISIONS.md` as `open`, and stop. Two
  agents can ping-pong forever without either being wrong.
- A gate fails for a reason the task does not cover.
- The change touches auth, payments, migrations, secrets, or user-data deletion.
- You are about to do something irreversible: force push, history rewrite,
  dropping a table, deleting someone else's branch.

Escalate by writing the question into `.agents/STATE.md` under Open Risks and
ending your turn. Do not guess and proceed.

### Never

Write secrets, tokens, or credentials into any tracked file, including the
`.agents/` files. Redact before pasting output into a handoff.

<!-- gridmatrix:end -->

>>>> FILE: CLAUDE.md
# CLAUDE.md

@AGENTS.md

Everything above applies. This file adds only Claude Code mechanics. Shared
rules live in `AGENTS.md`; do not restate them here.

## Claude Code specifics

- `@AGENTS.md` is an import. It expands inline at launch and counts against
  context, so keep both files lean.
- Project-root `CLAUDE.md` survives `/compact`; conversation context does not.
  After any `/compact`, re-read `.agents/STATE.md` and `.agents/HANDOFF.md`
  before continuing.
- Run `/memory` if unsure which instruction files are loaded.
- Auto-memory is local to this machine. Never treat it as shared state. Anything
  the other agent needs goes in `.agents/`, tracked in git. Codex cannot see
  Claude Code's memory; the filesystem is the only shared channel.

## Skills

`gridmatrix-session-start`, `gridmatrix-audit`, `gridmatrix-handoff`, and
`gridmatrix-adopt`. Installed globally and shared with Codex, so each procedure
exists once rather than once per tool. Invoke by name for determinism; the model
may also select them.

## Enforcement over instruction

Instruction files are context, not enforcement. For anything that must never
happen (committing to `main`, force push, destructive shell commands), add a
`PreToolUse` hook in `.claude/settings.json` instead of trusting a markdown
line. Prefer the hook whenever the cost of a miss is high.

>>>> FILE: .agents/STATE.md
# STATE

Current picture of the project. Read at every session start. Edit only when
something here actually changed. Cap 120 lines; over cap, cut the oldest
resolved risk rather than appending.

Last updated: NEVER (agent: none)

## Objective

<!-- One paragraph. What "done" means for the current phase, not the current task. -->
PLACEHOLDER

## Constraints

<!-- True and not negotiable away by either agent. -->
- PLACEHOLDER

## Architecture decisions in force

<!-- One line each with its DECISIONS.md ID. Do not re-argue these. -->
- PLACEHOLDER (see D-000)

## Open risks

| ID  | Risk | Impact | Owner | Status |
| --- | ---- | ------ | ----- | ------ |
| R-1 |      |        |       | open   |

## Open questions for the human

<!-- Anything an agent escalated and is blocked on. Empty is valid. -->
- none

## Known broken

<!-- Currently failing and NOT anyone's active task. Be honest: an empty list
     that is a lie costs the next agent an hour. -->
- none

>>>> FILE: .agents/TASKS.md
# TASKS

The queue and the lock. To claim, set `owner` and `status`, then commit this
file **alone** as `chore(agents): claim T-XXX`. A conflict on that commit means
someone else claimed it first.

Status: `spec` | `ready` | `building` | `auditing` | `resolving` | `done`
Owner: `claude-code` | `codex` | `-`

`owner` is the BUILDER and is set by the claim commit. `auditor` is set when the
task moves to `auditing`, and must be the platform that is **not** the owner.
Whoever built a task does not audit it.

## Active

### T-001 PLACEHOLDER title

- owner: `-`
- auditor: `-`
- status: `spec`
- branch: `-`

**Scope (in):**
- PLACEHOLDER

**Scope (out):**
- PLACEHOLDER

**Acceptance criteria** (checkable by someone not in the conversation):
1. PLACEHOLDER
2. PLACEHOLDER

## Backlog

<!-- Out-of-scope things spotted during work land here. Never fix them inline. -->

- [ ] PLACEHOLDER

## Done

<!-- Move here on merge, one line each. -->

>>>> FILE: .agents/HANDOFF.md
# HANDOFF

Written by the outgoing agent. Overwrite, do not append. Current edge of the
work only. Cap 100 lines. Use the `gridmatrix-handoff` skill.

**From:** none  **To:** none  **Task:** none  **Branch:** none  **Date:** never

## 1. What I did

<!-- Facts, not narrative. What changed, in which files, why. -->

## 2. What I did NOT do

<!-- The most important section. Anything in scope left undone, any path not
     exercised, any test skipped. The next agent has no memory of your session
     and will assume coverage that does not exist. -->

## 3. Evidence

<!-- Commands and their ACTUAL output, pasted. Not a summary. Label each claim
     verified / inferred / assumed. -->

```
$ PLACEHOLDER
```

## 4. Known broken right now

<!-- If everything passes, say so and show the gate output. -->

## 5. Next action

<!-- One concrete action. Not a list of options. -->

## 6. Open questions

<!-- Include what would settle each one. -->

>>>> FILE: .agents/REVIEW.md
# REVIEW

Findings from the AUDITOR, dispositioned by the BUILDER, cleared on merge.
Cap 150 lines. Use the `gridmatrix-audit` skill.

**Task:** none  **Auditor:** none  **Diff:** `git diff <base>...<head>`

The auditor reports and does not fix. Read the spec and the diff before reading
the builder's handoff notes.

## Findings

### F-1 [S0|S1|S2|S3] Short title

- **Location:** `path/to/file.ext:123`
- **Problem:** what is wrong, specifically
- **Reproduction:** the command, input, or exact path through the code that
  demonstrates it
- **Disposition** (builder fills): `fixed <commit>` | `waived: <reason>` |
  `deferred: T-XXX`

## What I verified

<!-- Commands the auditor actually re-ran, with results. Do not trust the
     builder's pasted output; reproducing it is the point of a second agent. -->

```
$ PLACEHOLDER
```

## What I could NOT verify

<!-- Required. Empty here is almost certainly a rubber stamp. -->

## Attack attempted

<!-- The input or condition you tried in order to break it, and what happened.
     Report it whether or not it worked. -->

## Verdict

`blocked (S0/S1 open)` | `pass with S2/S3 noted` | `pass`

>>>> FILE: .agents/DECISIONS.md
# DECISIONS

Append only. Never edit or delete an entry; supersede it with a new one that
references the old ID.

This exists so two stateless agents stop re-arguing the same choice every third
session. Before proposing an architectural change, read this file. If your
proposal contradicts an `accepted` entry, reference and rebut it explicitly
rather than silently rebuilding.

Log: any new dependency, any architectural choice, any deviation from
`AGENTS.md`, any deadlock escalated to the human.

## D-000 Adopt the two-agent protocol

- **Date:** PLACEHOLDER
- **Status:** accepted
- **Decided by:** human
- **Context:** Claude Code and Codex both work this repository with no shared
  memory and no direct channel.
- **Decision:** Coordinate through `.agents/` and git. The agent that builds a
  change does not audit it.
- **Consequences:** Every task carries a spec and an audit before merge. Costs
  roughly one extra session per task; buys a fresh-context reader on every diff.
- **Supersedes:** none

## Calibration

Alternating roles by task ID is a starting guess, not a finding. Log outcomes
here and let evidence from this repo replace the default. Generic claims about
which model is better at what do not survive contact with a specific codebase
and go stale every release. Ten tasks is enough to notice a pattern, not enough
to prove one: do not rewrite the rule off two data points.

| Task  | Builder | Auditor | Class | S0/S1 caught | Escaped | Rounds | Note |
| ----- | ------- | ------- | ----- | ------------ | ------- | ------ | ---- |
| T-001 |         |         |       |              |         |        |      |

>>>> FILE: .agents/FLAGS.md
# FLAGS

Cross-agent observations. Append only; `gridmatrix-retro` prunes. Cap 150 lines.

This is the channel for anything you notice **outside** your own task: work of
the other agent's that is wrong, a handoff that misled you, a stale STATE, or
the two of you in the same files. Nothing said only in your reply reaches the
other agent. If it is not written here, it did not happen.

The bar: would the other agent change what it does next if it knew? If not, do
not flag it.

**Types.** `COLLISION` same branch, worktree, or files, so stop and raise it
before writing anything else. `DEFECT` completed work is wrong, found outside an
audit, so include a reproduction. `FRICTION` something cost you time that a
written rule would have prevented; nobody has to be at fault, and these are what
retro turns into conventions.

**Status.** `open` needs an answer before the recipient starts new work and
blocks merge under gate 6. `resolved` says what was done. `disputed` says why
you disagree and escalates to the human rather than blocking forever.

---

## F-001 [FRICTION] Example, delete on first real flag

- raised by: `-`
- to: `-`
- status: `resolved`
- task: `-`
- what: one or two sentences, specific enough to act on
- evidence: command, `file:line`, or commit
- resolution: filled by the recipient

<!-- Newest at the bottom. Never edit another agent's flag text; add your
     resolution line to it instead. -->
