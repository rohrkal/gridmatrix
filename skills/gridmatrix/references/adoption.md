# Adoption and migration

Prerequisites: Python 3.9+ and Git. Works on Windows with Python/Git, macOS and
Linux. Use `python` instead of `python3` where appropriate. This installer is
project-local; it never changes global agent settings or installs launch hooks.

## New or inherited project

- Existing Git repository: inspect root, branches, status, instruction files,
  project manifests and prior coordination state. Work from a clean dedicated
  checkout if another session owns the current directory.
- Starting from zero: create the requested project directory and `git init` if
  authorized by the task. No commit is needed for installation. Before claiming a
  coding task, commit the reviewed scaffold/config explicitly; never stage broadly
  in an inherited dirty project.
- Claude-only or Codex-only history: preserve all existing instruction text.
  Record shared project facts in `.gridmatrix/PROJECT.md` with their provenance so
  both platforms can read them. A file's platform name does not decide which
  conflicting rule wins. User intent and applicable instruction precedence do.
- Both histories: compare objectives, architecture decisions, known failures,
  active branches and uncommitted changes. Resolve material contradictions from
  evidence; ask only when the user's intent genuinely cannot be determined.

Run the script from this skill directory (an absolute path avoids cwd ambiguity):

```sh
python3 /path/to/gridmatrix/scripts/gridmatrix.py --repo /path/to/project init --dry-run
python3 /path/to/gridmatrix/scripts/gridmatrix.py --repo /path/to/project init --remote origin
```

Choose `--remote origin` when agents use different clones, machines, or cloud
sandboxes. Confirm that origin is the intended shared project repository. This
records its name in project config; the first ledger request creates the separate
`gridmatrix-state` branch there. Both actors must have read/write access to that
branch. Normal source branches and indexes are untouched by ledger transactions.
Commit the config and installed project skills so another clone uses the same
transport. Never merge the coordination branch into a source branch.

Omit `--remote` only for agents using worktrees of the **same local Git repository**.
Its ledger is stored in `refs/gridmatrix/state`, shared through Git's common dir.
It is not synchronized by ordinary pushes and is not a backup. Independent clones
in local mode are separate coordinators: never use them for concurrent work.

`init` preserves existing transport on reruns, refuses implicit transport changes,
adds only a marked `AGENTS.md` block and exact `@AGENTS.md` import in `CLAUDE.md`,
and installs the complete skill under `.agents/skills/gridmatrix` and
`.claude/skills/gridmatrix`. It is idempotent, preflights paths/markers and refuses
symlink destinations. Its managed skill files are replaced on update; maintain
project customizations outside those files. Rerun from an updated upstream skill
copy to update both project copies. Old extra custom files are not removed;
`check` catches divergence between copies.

Fill PROJECT.md from the current request, manifests, lockfiles and code. Inspect
scripts before executing them. Record applicable commands and actual results,
including unavailable commands and pre-existing failures. Multiple lockfiles may
represent separate subprojects, not necessarily an erroneous README. Do not run
installation, deployment, migrations, or a costly suite automatically without
considering existing authorization and project requirements.

Run `check` for structural validation. It does not certify adoption facts or run
the project's tests. Verify each agent actually discovers this skill: invoke
`$gridmatrix` in Codex or `/gridmatrix` in Claude Code. Higher-precedence personal
skills or `AGENTS.override.md` may shadow project instructions; diagnose and tell
the user instead of silently changing global configuration.

## Migrating v1

Quiesce both writers first. Preserve `.agents/{STATE,TASKS,HANDOFF,REVIEW,DECISIONS,FLAGS}.md`
and inspect open tasks/flags before accepting new claims. Run the v2 installer,
which replaces only Gridmatrix's marked rules and preserves other text. Translate
active tasks into ledger claims, open flags into notices, and useful decisions
into PROJECT.md / proposed lessons. Never carry a v1 audit forward as approval of
an unverified head. Record source file/commit for every migrated record.

Resolve obsolete references to `gridmatrix-adopt`, `-audit`, `-handoff`, `-retro`,
and `-session-start` in inherited instructions explicitly, preserving unrelated
rules. After reconciling all active state, mark legacy files as historical and
remove old project skill copies only after confirming they are Gridmatrix-owned.
The single `gridmatrix` skill now contains all five procedures. Personal v1 skills
may need disabling in their platform UI; do not delete unrelated skills.

## Recovery and channel limits

If a writer disappears, inspect its worktree/branch and user-visible task state.
Do not steal ownership because a timer elapsed. Once that writer has stopped,
resume its recorded session identity only with explicit user-directed recovery,
or have the owner issue `transfer` to a new session of the same platform, from
the destination clean worktree, with evidence. Transfer invalidates approval.
For a different builder platform, close/split the task and review contributions
independently; never erase the original builder's identity.

To switch local/remote transport, stop both agents, export `ledger.json` from the
old ledger commit, preserve its commit history in the new coordination ref, and
verify matching content before changing config in both checkouts. This release
intentionally has no automatic migration or stale-lock takeover command.

A GitHub connector alone is not a local Git transport. If the runtime lacks a
Git-authenticated checkout, use available authorized integration capabilities to
obtain one, or leave a precise manual relay. Report that live coordination is
unavailable until both actors can read and atomically write the same ledger. Do
not promise that installing a Markdown skill grants credentials or starts agents.
