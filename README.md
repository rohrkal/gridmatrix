# gridmatrix

A shared working protocol for **Claude Code + Codex**: one owner per task,
independent reviews, explicit problem reporting, and project memory that improves
with use. One portable skill with a Python/Git runtime. **Version 2.1.0.**

## Start on any project

Requires Python 3.9+ and Git 2.38+ for integration checks. Clone this repository, then:

```sh
python3 /path/to/gridmatrix/gridmatrix.py --repo /path/to/project init --remote origin
```

For a new project, create its directory and run `git init` first. If both agents
use worktrees of the same local repository, omit `--remote origin`. Use remote
mode for separate clones, computers, or cloud sandboxes. Both need access to the
same configured Git remote. Paths containing spaces are supported when quoted.

The installer preserves existing `AGENTS.md` and `CLAUDE.md` rules, adds the shared
entrypoint, and installs the same `gridmatrix` skill for both platforms. Commit
those reviewed setup files so teammates and cloud clones receive them.

In Codex, invoke **`$gridmatrix`**. In Claude Code, invoke **`/gridmatrix`**.
Then ask: “Adopt this project, preserve existing decisions, and coordinate the
next task with the other platform.” The skill performs adoption and continues
useful authorized work in the same turn.

## What changes

| Need | Gridmatrix behavior |
| --- | --- |
| Avoid collisions | Atomic claims reject overlapping paths, reused branches and working directories. Parallel writers use separate worktrees. |
| Communicate reliably | Git-backed records with unique IDs, retry deduplication, explicit recipient acknowledgments and evidence. |
| Expose mistakes | Both agents must report defects, collisions and changed assumptions. Critical notices block affected tasks until verified resolved. |
| Improve quality | Bounded peer spec/review runs, captured checks, exact-commit approval and tests against the current integration target. |
| Respect dependencies | Claims require completed prerequisites in the source branch; pinned shared interfaces detect logical conflicts. |
| Recover interruptions | Explicit operator recovery preserves old/new identities and keeps unresolved defects blocking. |
| Build on strengths | Roles follow demonstrated project experience and outcomes, with independent review covering the builder's blind spots. |
| Learn together | Scoped lessons become active only after the other platform validates them. Record whether lessons help or recur; compare rework and escaped defects on similar tasks. Ten active lessons maximum. |
| Adopt existing work | Preserve inherited instructions and unfinished work; migrate prior decisions instead of starting over. |

## How communication works

The helper maintains a separate coordination ledger. Remote mode uses the
`gridmatrix-state` branch; local mode uses a shared Git ref across worktrees.
Concurrent writes are retried against fresh state, never force-pushed. Task code
travels on ordinary source branches. Ledger writes do not alter source worktrees
or their indexes.

**Recorded is different from acknowledged.** Active agents check messages at
work boundaries. When the execution environment has authenticated CLIs, the
runtime can launch the other platform for a bounded, read-only spec check or
review. Otherwise it leaves a durable handoff for the next session. Missing
execution, failed runs and invalid responses never become peer approval.

| Platform capability | Gridmatrix use |
| --- | --- |
| Claude Code headless + JSON Schema | Structured reviews with tool, turn and spend limits |
| Codex exec + JSON events | Read-only structured reviews with time/output/run limits |
| Codex App Server | Streaming review turns, session provenance and explicit failed-turn resume |
| Claude hooks | Opt-in ownership/scope checks; strict mode denies shell tools |
| MCP stdio | Identity-bound coordination tools backed by the same ledger |
| Git worktrees + CI | Isolated writers/reviewers and tested integration candidates |

Run `doctor` to discover available capabilities. The adapters have controlled
subprocess coverage; **live Claude/Codex compatibility is still awaiting validation
on an authenticated installation**. Commands, configuration and limits are in
[execution.md](skills/gridmatrix/references/execution.md).

The runtime captures real command exit codes and logs. It cannot determine whether
a test suite is adequate, intercept every external edit, or cryptographically
attest model identity. Keep platform permissions and project protections.

## Maintain and verify

```sh
# Preview an install/update without writing
python3 gridmatrix.py --repo /path/to/project init --dry-run
# Update managed files from this checkout, preserving project state
python3 gridmatrix.py --repo /path/to/project init
# Validate installation, then refresh coordination
python3 gridmatrix.py --repo /path/to/project check
python3 gridmatrix.py --repo /path/to/project status
python3 gridmatrix.py --repo /path/to/project doctor
# Validate the actual helper
python3 -m unittest discover -s tests -v
```

`check` verifies structure; it does not claim your application tests pass.
`check --task T-001` additionally requires approval at the current clean HEAD and
passing integration evidence against an unchanged target.
The task owner integrates within the user's authorization and validates the
integration result. Gridmatrix never automatically merges or deploys code.

The canonical skill is [skills/gridmatrix/SKILL.md](skills/gridmatrix/SKILL.md).
[Adoption and migration](skills/gridmatrix/references/adoption.md) covers new,
Claude-first, Codex-first, mixed-history and disconnected environments.
Existing v2.0 ledgers need the documented schema upgrade after both platforms
receive v2.1; new projects initialize directly.
The former `files/` upload layout is superseded; its original contents remain
in Git history. Do not run its old installer alongside v2.

See [review findings](docs/review-findings.md) for the problems corrected and
validation limits. Platform discovery paths follow the official
[Codex skill documentation](https://developers.openai.com/codex/skills) and
[Claude Code skill documentation](https://code.claude.com/docs/en/skills).
