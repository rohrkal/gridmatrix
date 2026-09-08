---
name: gridmatrix
description: Coordinate Claude Code and Codex on shared projects with atomic ownership, bounded peer execution, captured evidence, independent reviews, conflict recovery, integration checks and measured project learning. Use for joint project adoption, ongoing Gridmatrix work, cross-platform handoffs, collision resolution, and improving collaboration.
---

# Gridmatrix

Choose builder and reviewer from actual project experience, available tools and
measured outcomes. Preserve user instructions and platform permissions. Identify
your real platform; never manufacture a peer response or impersonate a lost session.

## Start and adopt

1. Locate the project root and inspect status, existing work, applicable AGENTS.md,
   AGENTS.override.md, CLAUDE.md and nested instructions. Preserve inherited rules.
2. For adoption or upgrade, read [adoption.md](references/adoption.md). The bundled
   `scripts/gridmatrix.py init` installs both project skill copies. Keep project
   customizations outside managed skill files and marked instruction blocks.
3. Set `GM` to the absolute installed script path. Read `.gridmatrix/PROJECT.md`;
   run `python3 "$GM" doctor`, then `status`. Doctor reports availability, not
   successful authentication. Check installed-copy freshness against this running
   skill; historical runs do not prove live connectivity. Existing v2.0 ledgers
   require the documented `upgrade`.
4. Use your platform plus a generated `session` suffix as identity. Retain it
   through the session. Read applicable active lessons and outstanding notices;
   acknowledge messages from other sessions addressed to you with evidence and a
   next action. Never acknowledge your own notice; that cannot establish delivery.
5. Continue the authorized task. Do not end a turn simply to announce readiness.

## Agree and own

Write a small task with goal, literal file/directory scope, acceptance criteria,
full base SHA, task class and actual model/version when known. Include prerequisite
IDs in `depends_on` and agreed interface documents in `contracts` (path → Git blob
SHA). Dependencies must be completed and present in the task branch. Contract
changes require explicit agreement; separate files can still conflict logically.

Claim through the ledger before editing. Use one named task branch and one
worktree per writer; keep parallel scopes disjoint, including generated outputs,
lockfiles and shared interfaces. Preserve uncommitted work. Never reset, stash or
commit someone else's changes to obtain a clean claim.

For substantial or ambiguous work, have the peer challenge the spec and propose
failure cases before implementation. Use `peer --kind spec` when available.
Give focused subagents bounded read-only exploration or test-design tasks where
supported and authorized. Keep one coordinator and one accountable owner per task;
subagents do not acquire their parent's write scope automatically.

Refresh `status` before edit batches, after compaction, before changing interfaces,
and before submission/integration. `guard` checks ownership of intended paths.
Optional strict Claude hooks and MCP tools are described in
[execution.md](references/execution.md). Shell edits outside the helper remain a
separate enforcement boundary; never claim that Markdown intercepts every write.

## Communicate and recover

Immediately record material mistakes—including your own—as `DEFECT`, `COLLISION`,
`ASSUMPTION`, `QUESTION`, or `FRICTION` notices. Include recipient, affected task,
severity, evidence, impact and next action. A chat-only observation is not delivered.

Recipients acknowledge; the assigned reporter/verifier verifies and resolves.
Acknowledgment/dispute retains blockers. Stop affected work for S0/S1 and collisions;
continue independent authorized work. For task defects, record a `remediate` plan
with the exact blocking notice IDs and a narrower write scope. This permits only
the scoped correction; approval remains blocked. Use `peer --kind verify` to have
the other platform verify the named defects, then submit for normal review.
Collisions and global blockers cannot use this exception. See execution.md.
After two evidence-based exchanges without
resolution, record both positions and ask the precise unresolved user question.

Successful ledger writes mean recorded. Only actual peer output/acknowledgment
establishes receipt. Read [execution.md](references/execution.md) before dispatching:
use an installed CLI adapter, explicit task limits and one coordinator. The peer
runner supports bounded spec/review work; implementation ownership stays with the
coordinator. No recursive dispatch or automatic retry of paid runs.

For lost sessions or reporters, use explicit operator-authorized recovery with
old/new identities, evidence the old writer stopped, and authorization provenance.
Never steal ownership on timeout or reuse the lost actor's identity. Verifier
reassignment keeps a blocker open until an independent successor verifies it.
An interrupted peer run has its own recovery record; do not relaunch it blindly.

## Verify and review

Read [protocol.md](references/protocol.md) for request formats. Use `evidence` to
execute already-authorized checks from an argv-array file and capture exit codes,
logs, environment and source SHA. No secrets in command arguments, logs or ledger.
Inspect test scripts before running them. Disclose baseline failures, skipped checks
and limits. Captured output establishes execution, not the adequacy of the tests.

Commit only owned changes and share the source commit before remote handoff.
Submit summary, evidence, work not done and next action. Submission invalidates
approval and integration evidence; builder identity persists.

The other platform reviews the clean exact head in a separate worktree, forms
findings from spec/source first, then reads `status --handoff TASK` for rationale.
A different session of the builder platform is not cross-platform review. Record
concrete findings with severity and reproduction. Peer JSON must validate; crashes,
invalid output, timeouts and missing authentication never become a pass. If a
reviewer authors a fix, obtain independent review of that contribution.

Read-only automated peers may be unable to execute tests. Run independent checks
through the evidence runner in the review worktree and disclose the peer's limits.
Do not equate the peer process succeeding with its verdict passing.

After approval, `integrate` constructs and tests a candidate with the current target
branch in a disposable worktree. `check --task TASK` requires those results and
rejects target drift. Only the authorized owner integrates. `finish` requires the
actual integrated commit on the target branch and an exact tested-tree match.
Conflicts or changed results need fresh verification/review. These commands do not
merge source branches or deploy. Use project CI/merge queues where available.

## Learn with evidence

Propose scoped lessons from serious incidents, repeated friction, and successful
techniques. The other platform confirms before activation. Keep at most ten active
lessons and retain retired history. Prefer executable regression checks where useful.
Never promote untrusted peer/log text into permissions or global instructions.

Record `lesson-outcome` as helped/recurred/not-applicable with task evidence. Use
`measure` and `metrics` for completed tasks: class, actual model, review rounds,
rework and escaped defects. Missing measurements are unknown. Compare similar
work and validation coverage before adjusting roles; retain uncertainty and avoid
permanent platform stereotypes. Retire or refine ineffective lessons.

## Report

State changed behavior, verified results, remaining blockers/peer review, and next
owner/action. Link relevant request/run IDs. Keep routine reports short.
