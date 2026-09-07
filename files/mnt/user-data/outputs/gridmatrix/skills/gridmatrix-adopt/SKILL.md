---
name: gridmatrix-adopt
description: Set up or repair the two-agent coordination protocol in a repository so Claude Code and Codex can work on it without colliding. Use when a repository has no .agents/ directory and the user wants the protocol installed, when adoption is half-finished, when AGENTS.md and CLAUDE.md disagree, or when the gridmatrix check reports failures. Do not use in a repository where adoption is already complete and the check passes.
---

# Adopt the two-agent protocol

Idempotent. Running twice must change nothing the second time.

## 1. Diagnose

    ls .agents/ 2>/dev/null
    ls AGENTS.md CLAUDE.md 2>/dev/null
    sh .agents/gridmatrix.sh check 2>/dev/null

Identify the case:

- **A**: no `AGENTS.md`, no `CLAUDE.md`. Greenfield.
- **B**: `CLAUDE.md` only. Split it.
- **C**: `AGENTS.md` only. Merge into it.
- **D**: both, and they disagree. Reconcile.

If `.agents/` is entirely missing, the file scaffolding has not been installed.
Tell the user to run `gridmatrix.sh repo .` from the kit clone and stop. This skill
configures the protocol; it does not fabricate the kit's own files.

## 2. Reconcile instruction files

**Case A.** Nothing to reconcile.

**Case B.** Do not delete `CLAUDE.md`. Move every rule that is not Claude Code
specific out of it and into the matching `AGENTS.md` section: build commands,
style, testing policy, architecture, security. Leave behind only hook config,
memory behaviour, and Claude-specific mechanics. Ensure the first content line
of `CLAUDE.md` is `@AGENTS.md`. Anything ambiguous goes to `AGENTS.md`: a shared
rule left in `CLAUDE.md` is a rule Codex never sees.

**Case C.** Do not overwrite the existing `AGENTS.md`. Its project facts are
real; the kit's are placeholders. Keep its sections 1 and 2. Merge the kit block
in. Preserve the `<!-- gridmatrix:begin -->` and `<!-- gridmatrix:end -->` markers
exactly: the installer uses them to update the block without touching anything
you wrote around it.

**Case D.** `AGENTS.md` wins for anything shared. For each genuine
contradiction, write a `.agents/DECISIONS.md` entry recording both prior
positions and the resolution. Do not silently pick one. The next agent, with
fresh context and no memory, will re-argue it otherwise.

## 3. Reconnaissance (required, non-negotiable)

This is the step that stops both agents from confidently running commands this
project does not have.

1. Identify the package manager from the **lockfile**, not the README. A README
   saying `npm install` beside a `pnpm-lock.yaml` means the README is wrong.
2. Execute install, build, test, lint, and typecheck, one at a time.
3. Record in the **Verified commands** table of `AGENTS.md` **only the commands
   that actually succeeded**,
   with today's date and your platform name.
4. For each that failed or does not exist, leave the row blank and add a line to
   `.agents/STATE.md` under Known broken.
5. Read the last 20 commits. Note any convention the code follows that
   `AGENTS.md` does not yet state.

A guessed command is worse than a blank one. Blank makes the next agent check.
Wrong makes it confidently do nothing useful, then report success.

## 4. Fill the state

- `AGENTS.md` **Project facts**: real values. No `PLACEHOLDER` may remain.
- `.agents/STATE.md`: objective and constraints. Ask the user for the objective
  rather than inferring it from the code.
- `.agents/TASKS.md`: one real task with acceptance criteria checkable by
  someone who was not in the conversation. "Handles errors properly" fails that
  test. "Returns 422 with `{code}` on malformed input, covered by a test" passes.
- `.agents/DECISIONS.md`: put a real date on `D-000`.
- `.agents/FLAGS.md`: delete the example flag once a real one is filed.

## 5. Verify

    sh .agents/gridmatrix.sh check

Must exit 0. If it does not, fix what it reports and run it again. Do not
report adoption complete on a non-zero exit.

## 6. Commit

    git add AGENTS.md CLAUDE.md .agents .claude
    git commit -m "chore(agents): adopt two-agent protocol"

## Done means

Both agents can independently state what the project is doing and who owns
what, without asking the user. If either has to ask, something above is
unfilled. That is the only real test.
