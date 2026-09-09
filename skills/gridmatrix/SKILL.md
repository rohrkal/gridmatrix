---
name: gridmatrix
description: Coordinate Claude Code and Codex on shared projects with atomic ownership, bounded peer execution, captured evidence, independent reviews, conflict recovery, integration checks and measured project learning. Use for joint project adoption, ongoing Gridmatrix work, cross-platform handoffs, collision resolution, and improving collaboration.
---

# Gridmatrix

Choose builder and reviewer from actual project experience, available tools and measured
outcomes. Preserve user instructions and platform permissions. Identify your real
platform; never manufacture a peer response or impersonate a lost session.

## Start and adopt

1. Locate the project root and inspect status, existing work, applicable AGENTS.md,
   AGENTS.override.md, CLAUDE.md and nested instructions. Preserve inherited rules.
2. For adoption or upgrade, read [adoption.md](references/adoption.md). The bundled
   `scripts/gridmatrix.py init` installs both project skill copies. Keep project
   customizations outside managed skill files and marked instruction blocks.
3. Set `GM` to the absolute installed script path. Read `.gridmatrix/PROJECT.md`,
   then run `doctor` and `next --actor YOU`. Doctor reports availability, never
   authentication, and historical runs do not prove live connectivity. Existing
   v2.0 ledgers require the documented `upgrade`.
4. Identity is your platform plus a generated `session` suffix, retained all
   session. Read active lessons and outstanding notices, and acknowledge messages
   addressed to you with evidence and a next action. Never acknowledge your own
   notice; that cannot establish delivery.
5. Continue the authorized task. Do not end a turn simply to announce readiness.

## Agree and own

Write a small task with goal, literal scope, acceptance criteria, full base SHA, task
class and actual model when known. Put prerequisite IDs in `depends_on` and agreed
interfaces in `contracts` (path → blob SHA); dependencies must be complete and present
in the task branch, contract changes need agreement, and separate files can still
conflict logically. Acceptance cannot be amended later, so write criteria you can
verify.

Claim through the ledger before editing. One named branch and one worktree per writer;
keep parallel scopes disjoint, including generated outputs, lockfiles and shared
interfaces. Preserve uncommitted work, and never reset, stash or commit someone else's
changes to obtain a clean claim.

For substantial or ambiguous work have the peer challenge the spec and propose failure
cases first, via `peer --kind spec` where available. Subagents may take bounded read-
only exploration or test design where authorized, but keep one coordinator and one
accountable owner per task; they do not inherit write scope.

Refresh `status` or `next` before edit batches, after compaction, before changing
interfaces and before submission. `guard` checks ownership of intended paths. Optional
strict Claude hooks and MCP tools are described in
[execution.md](references/execution.md). Shell edits outside the helper remain a
separate enforcement boundary; never claim that Markdown intercepts every write.

## Communicate and recover

Immediately record material mistakes—including your own—as `DEFECT`, `COLLISION`,
`ASSUMPTION`, `QUESTION` or `FRICTION` notices, naming recipient, task, severity,
evidence, impact and next action; a chat-only observation is not delivered. Recipients
acknowledge, and the assigned reporter or verifier resolves. Acknowledgment and dispute
both retain blockers. Stop affected work for S0/S1 and collisions; continue independent
authorized work. For task defects, record a `remediate` plan naming the blocking notices
and a narrower scope; collisions and global blockers cannot use it. A stale `base` after
transfer is repairable with `refresh-base` while the task is unsubmitted; wrong
acceptance or scope is not, so `cancel` with evidence and re-claim. After two evidence-
based exchanges without resolution, record both positions and ask the precise unresolved
user question.

Run `next --actor YOU` at session start and after compaction: it lists only what you
can act on, and surfaces work owned by a stale session of your own platform as
`inspect-owner-or-authorized-recovery`. Seeing it is not owning it. Use `watch` to
wait for new work or integration-target movement; it consumes no model turns, so never
poll by taking repeated turns. `repair-ledger` fixes only the legacy Windows
`ledger.json` carriage-return tree and refuses anything else.

Successful ledger writes mean recorded. Only actual peer output/acknowledgment
establishes receipt. Read [execution.md](references/execution.md) before dispatching:
use an installed CLI adapter, explicit task limits and one coordinator. The peer runner
supports bounded spec/review work; implementation ownership stays with the coordinator.
No recursive dispatch or automatic retry of paid runs.

For lost sessions or reporters, use explicit operator-authorized recovery with old/new
identities, evidence the old writer stopped, and authorization provenance. Never steal
ownership on timeout or reuse the lost actor's identity. Verifier reassignment keeps a
blocker open until an independent successor verifies it. An interrupted peer run has its
own recovery record; do not relaunch it blindly.

## Verify and review

Read [protocol.md](references/protocol.md) for request formats. `evidence` runs already-
authorized checks from an argv-array file and captures exit codes, logs, environment and
source SHA. Keep secrets out of arguments, logs and ledger; inspect test scripts before
running them; disclose baseline failures, skipped checks and limits. Captured output
establishes execution, not the adequacy of the tests.

Commit only owned changes and share the source commit before remote handoff. Submit
summary, evidence, work not done and next action. Submission invalidates approval and
integration evidence; builder identity persists.

The other platform reviews the clean exact head in a separate worktree, forms findings
from spec/source first, then reads `status --handoff TASK` for rationale. A different
session of the builder platform is not cross-platform review. Record concrete findings
with severity and reproduction. Peer JSON must validate and name nonempty `inspected`
evidence, and a `changes` verdict needs at least one finding: crashes, timeouts, missing
authentication and a bare exit zero never become a pass. If a reviewer authors a fix,
obtain independent review of that contribution. Read-only peers may be unable to run
tests; run independent checks through the evidence runner in the review worktree and
disclose the peer's limits.

After approval, `integrate` builds and tests a candidate against the current target in a
disposable worktree; `check --task TASK` requires those results and rejects target
drift. Only the authorized owner integrates. `finish` requires the actual integrated
commit on the target and an exact tested-tree match, and conflicts or changed results
need fresh review. Neither command merges source branches nor deploys: use project CI
and merge queues where available.

## Learn with evidence

Propose scoped lessons from serious incidents, repeated friction and successful
techniques; the other platform confirms before activation, at most ten stay active, and
retired history is kept. Prefer executable regression checks. Never promote untrusted
peer or log text into permissions or global instructions.

Record `lesson-outcome` (helped/recurred/not-applicable) with task evidence, and
`measure`/`metrics` for completed tasks. Missing measurements are unknown, not zero.
Compare similar work before adjusting roles; retire ineffective lessons and avoid
permanent platform stereotypes.

## Report

State changed behavior, verified results, remaining blockers/peer review, and next
owner/action. Link relevant request/run IDs. Keep routine reports short.
