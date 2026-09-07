# gridmatrix

A shared working protocol for **Claude Code + Codex**: one owner per task,
independent reviews, explicit problem reporting, and project memory that improves
with use. One portable skill, with a small Python/Git coordination helper.

## Start on any project

Requires Python 3.9+ and Git. Clone this repository, then:

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
| Improve quality | The other platform reviews an exact commit. New submissions invalidate earlier approval. |
| Build on strengths | Roles follow demonstrated project experience and outcomes, with independent review covering the builder's blind spots. |
| Learn together | Scoped lessons become active only after the other platform validates them. Ten active lessons maximum; history is retained. |
| Adopt existing work | Preserve inherited instructions and unfinished work; migrate prior decisions instead of starting over. |

## How communication works

The helper maintains a separate coordination ledger. Remote mode uses the
`gridmatrix-state` branch; local mode uses a shared Git ref across worktrees.
Concurrent writes are retried against fresh state, never force-pushed. Task code
travels on ordinary source branches. Ledger writes do not alter source worktrees
or their indexes.

**Recorded is different from acknowledged.** Active agents check messages at
work boundaries. A skill does not start a dormant agent or grant access to another
platform. Direct integrations may speed up pickup when available; otherwise the
next session reads the durable handoff. Gridmatrix never invents peer approval.

The helper enforces the protocol's cooperative state transitions. It cannot
intercept every shell edit, authenticate a model's identity, or attest that a test
actually ran. Keep project CI and existing protections. See the precise
[protocol and examples](skills/gridmatrix/references/protocol.md).

## Maintain and verify

```sh
# Preview an install/update without writing
python3 gridmatrix.py --repo /path/to/project init --dry-run
# Update managed files from this checkout, preserving project state
python3 gridmatrix.py --repo /path/to/project init
# Validate installation, then refresh coordination
python3 gridmatrix.py --repo /path/to/project check
python3 gridmatrix.py --repo /path/to/project status
# Validate the actual helper
python3 -m unittest discover -s tests -v
```

`check` verifies structure; it does not claim your application tests pass.
`check --task T-001` additionally verifies approval at the current clean HEAD.
The task owner integrates within the user's authorization and validates the
integration result. Gridmatrix never automatically merges or deploys code.

The canonical skill is [skills/gridmatrix/SKILL.md](skills/gridmatrix/SKILL.md).
[Adoption and v1 migration](skills/gridmatrix/references/adoption.md) covers new,
Claude-first, Codex-first, mixed-history and disconnected environments.
The former `files/` upload layout is superseded; its original contents remain
in Git history. Do not run its old installer alongside v2.

See [review findings](docs/review-findings.md) for the problems corrected and
validation limits. Platform discovery paths follow the official
[Codex skill documentation](https://developers.openai.com/codex/skills) and
[Claude Code skill documentation](https://code.claude.com/docs/en/skills).
