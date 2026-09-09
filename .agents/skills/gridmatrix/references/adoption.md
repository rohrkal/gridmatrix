# Adoption and migration

Prerequisites: Python 3.9+ and Git (2.38+ for integration checks). The suite now runs on
Windows as well as POSIX, though strict hook auto-install remains POSIX-only. On Windows
use `python`, since `python3` is often a Store alias stub that exits without running.
The installer is project-local and never changes global agent settings or installs
launch hooks.

## New or inherited project

- **Existing repository:** inspect root, branches, status, instruction files,
  manifests and prior coordination state. Work from a clean dedicated checkout if
  another session owns the current directory.
- **From zero:** create the directory and `git init` if the task authorizes it.
  Installation needs no commit, but commit the reviewed scaffold before claiming a
  coding task; never stage broadly in an inherited dirty project.
- **Single-platform history:** preserve existing instruction text and record shared
  facts in `.gridmatrix/PROJECT.md` with provenance. A file's platform name does not
  decide which conflicting rule wins; user intent and precedence do.
- **Both histories:** compare objectives, decisions, known failures, active branches
  and uncommitted changes. Resolve contradictions from evidence; ask only when the
  user's intent genuinely cannot be determined.

Run the script from this skill directory (an absolute path avoids cwd ambiguity):

```sh
python3 /path/to/gridmatrix/scripts/gridmatrix.py --repo /path/to/project init --dry-run
python3 /path/to/gridmatrix/scripts/gridmatrix.py --repo /path/to/project init --remote origin
```

Choose `--remote origin` when agents use different clones, machines, or cloud sandboxes.
Confirm that origin is the intended shared project repository. This records its name in
project config; the first ledger request creates the separate `gridmatrix-state` branch
there. Both actors must have read/write access to that branch. Normal source branches
and indexes are untouched by ledger transactions. Commit the config and installed
project skills so another clone uses the same transport. Never merge the coordination
branch into a source branch.

Omit `--remote` only for agents using worktrees of the **same local Git repository**.
Its ledger is stored in `refs/gridmatrix/state`, shared through Git's common dir. It is
not synchronized by ordinary pushes and is not a backup. Independent clones in local
mode are separate coordinators: never use them for concurrent work.

`init` is idempotent: it preserves existing transport, refuses implicit transport
changes, adds only a marked `AGENTS.md` block and the `@AGENTS.md` import in
`CLAUDE.md`, installs the skill under `.agents/skills/gridmatrix` and
`.claude/skills/gridmatrix`, manages a `.gitattributes` block described below,
preflights paths and markers, and refuses symlink destinations. Managed skill files are replaced on update, so keep project customizations
outside them; extra custom files are never removed. `check` catches divergence between
copies and from the running skill, so check freshness with the intended updated script -
an old one cannot discover a newer release.

`init` also maintains a marked block in the project's `.gitattributes` pinning both
installed skill trees to `-text`, disabling end-of-line conversion so the bytes on
disk always match the bytes `check` compares. Without it, a project adopted where
`core.autocrlf=true` looks healthy to its author and then fails `check` for the next
person who clones it, because the installed skill returns with CRLF. The block sits
last because Git applies the final matching rule, so anything appended after it could
silently defeat the guarantee: `check` therefore rejects a stale or malformed block,
and rerunning `init` repairs it while preserving every user-owned rule. Malformed or
duplicated markers refuse rather than rewrite the file. Only the two installed trees
are pinned; `AGENTS.md`, `CLAUDE.md` and `.gridmatrix/` are read as text through
universal newlines, so conversion there is harmless and the project keeps its own
preferences everywhere else.

Fill PROJECT.md from the request, manifests, lockfiles and code, inspecting scripts
before executing them. Record applicable commands and their actual results, including
unavailable commands and pre-existing failures. Multiple lockfiles may mean separate
subprojects rather than a wrong README. Never run installation, deployment, migrations
or a costly suite automatically without considering existing authorization and project
requirements.

Run `check` for structural validation; it certifies neither adoption facts nor the
project's tests. Verify discovery by invoking `$gridmatrix` in Codex or `/gridmatrix`
in Claude Code. Installing for Claude Code takes two commands:
`/plugin marketplace add OWNER/REPO`, then `/plugin install gridmatrix@gridmatrix`.
Adding a marketplace does not install its plugin. Personal skills or
`AGENTS.override.md` can shadow project instructions; diagnose and tell the user
rather than silently changing global configuration.

## Upgrading an existing installation

Quiesce both writers and any in-flight peer runs first, then rerun `init` from the
updated skill so both project copies match, and commit the reviewed result.

- **From v2.1.x:** nothing else is required. Ledger schema stays 3.
- **From v2.0:** run `upgrade --actor PLATFORM:SESSION` once. The migration is
  atomic and preserves tasks, notices, lessons and receipts. Old actors reject
  schema 3 rather than bypass its gates. Existing approvals still need fresh
  integration evidence before `finish`.
- **From v1:** preserve `.agents/{STATE,TASKS,HANDOFF,REVIEW,DECISIONS,FLAGS}.md` and
  read open tasks and flags before accepting claims. Translate tasks into claims, flags
  into notices, and decisions into PROJECT.md or proposed lessons, recording the source
  file and commit for each; never carry a v1 audit forward as approval of an unverified
  head. Resolve inherited `gridmatrix-adopt`, `-audit`, `-handoff`, `-retro` and
  `-session-start` references explicitly - the single skill now contains all five. Mark
  legacy files historical, remove old skill copies only once confirmed Gridmatrix-owned,
  and disable a personal v1 skill in its platform UI.

Use a new request ID for a new submission: an identical old ID replays the recorded
request rather than starting a new lifecycle step.

[execution.md](execution.md) covers recovery, bounded execution and optional
integrations. Use explicit operator recovery rather than assuming a lost actor's
identity. A GitHub connector is not a local Git transport, both environments need the
configured coordinator, and no skill grants credentials or installs a peer CLI.
