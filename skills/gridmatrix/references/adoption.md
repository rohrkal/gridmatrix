# Adoption and migration

Prerequisites: Python 3.9+ and Git (2.38+ for integration checks). The core uses
portable Python/Git; Windows-specific behavior remains unvalidated. Strict hook
auto-install requires POSIX. Use `python` instead of `python3` where appropriate. This installer is
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
`check` catches divergence between copies and differences from the running skill
for its instructions, references and runtime files. Use the intended updated
upstream script when checking freshness; an old script cannot discover a newer
release by itself.

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

## Upgrading an existing installation

Quiesce both writers and any in-flight peer runs first, then rerun `init` from the
updated skill so both project copies match, and commit the reviewed result.

- **From v2.1.x:** nothing else is required. Ledger schema stays 3.
- **From v2.0:** run `upgrade --actor PLATFORM:SESSION` once. The migration is
  atomic and preserves tasks, notices, lessons and receipts. Old actors reject
  schema 3 rather than bypass its gates. Existing approvals still need fresh
  integration evidence before `finish`.
- **From v1:** preserve `.agents/{STATE,TASKS,HANDOFF,REVIEW,DECISIONS,FLAGS}.md`
  and read open tasks and flags before accepting new claims. Translate active
  tasks into claims, open flags into notices, and decisions into PROJECT.md or
  proposed lessons, recording the source file and commit for each. Never carry a
  v1 audit forward as approval of an unverified head. Resolve inherited references
  to `gridmatrix-adopt`, `-audit`, `-handoff`, `-retro` and `-session-start`
  explicitly; the single `gridmatrix` skill now contains all five procedures. Mark
  legacy files historical and remove old project skill copies only once confirmed
  Gridmatrix-owned. A personal v1 skill may need disabling in its platform UI.

Use a new request ID for a new submission. Reusing an identical old ID replays the
recorded request instead of starting a new lifecycle step.

Recovery, bounded execution and optional integrations are documented in
[execution.md](execution.md). Use explicit operator recovery instead of assuming a
lost actor's identity. A GitHub connector alone is not a local Git transport; both
environments need access to the configured coordinator. No skill grants credentials
or installs a peer CLI automatically.
