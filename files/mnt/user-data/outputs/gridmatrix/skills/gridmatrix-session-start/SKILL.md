---
name: gridmatrix-session-start
description: Load shared two-agent coordination state at the start of a coding session in a repository that uses the Claude Code / Codex protocol. Use when starting work, resuming after a break, after a context compaction, or when the user asks what the state of the project is or what to work on next. Do not use in repositories that have no .agents/ directory, and do not use for one-off questions that need no project state.
---

# Session start

## Guard

Check that `.agents/TASKS.md` exists at the repository root.

If it does not, this repository has not adopted the two-agent protocol. Say so
in one line, mention that `gridmatrix-adopt` can set it up, and stop. Do not invent
the files.

## Procedure

Run and read:

    git branch --show-current
    git status --short
    git log --oneline -15

Read, in this order:

1. `AGENTS.md`
2. `.agents/STATE.md`
3. `.agents/HANDOFF.md`
4. `.agents/TASKS.md`
5. `.agents/FLAGS.md`

Reconcile the git output against `.agents/STATE.md`. Git is the ground truth.
If they disagree, STATE is stale: correct STATE first and say that you did.

## Collision check

Do this before claiming anything. Self-report is not enough here; look at git.

    git worktree list
    git branch -a --sort=-committerdate | head

You are colliding if any of these is true: a task in `.agents/TASKS.md` is
`building` or `auditing` under the other agent's name and its branch is the one
you are on; there are uncommitted changes you did not make; or a branch for the
task you intend to claim already exists with commits on it.

If so, raise a `COLLISION` flag in `.agents/FLAGS.md` and stop. Do not "just be
careful" in a shared working directory. Two agents in one directory clobber each
other with no warning, and the loss is silent.

## Output

Report exactly four lines, then stop:

1. Platform, your role this session, and the task ID you are picking up.
2. What the previous session left undone (the "What I did NOT do" section).
3. Anything currently known broken, and any flag addressed to you that is still
   `open`. Open flags come before new work.
4. The single next action.

Do not write code in this turn. Do not claim a task in this turn. Claiming is a
separate, deliberate act, and doing it automatically defeats the lock.

If `.agents/TASKS.md` shows no task in a state you can pick up, say so and ask
which task to work on rather than choosing one yourself.
