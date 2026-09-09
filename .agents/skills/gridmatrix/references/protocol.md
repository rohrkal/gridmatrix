# Ledger protocol v3 (Gridmatrix 2.2.0)

## Commands

`python3 "$GM" --repo PATH init [--remote origin] [--dry-run]`
installs the project skill. `session` generates a session suffix. `status`
refreshes active tasks/notices/lessons without builder rationale. After independently
reading the spec and diff, use `status --handoff TASK` to retrieve that rationale.
`status --all` includes full history and handoffs; avoid it before independent review.
`apply request.json` (or `apply -` with JSON stdin) is the only write entrypoint.
`check` validates installation; `check --task T-001` additionally checks independent
approval against the current clean HEAD and outstanding blocking notices.
`next --actor ACTOR` lists only what that identity can act on.
`watch --actor ACTOR --timeout N` blocks until something newly actionable appears,
without consuming model turns. `repair-ledger --actor ACTOR` fixes only the legacy
`ledger.json` carriage-return tree, and is the only writer among these three.

Use a unique stable `id` per request; retry the *same* body and ID after ambiguous
network failure. An identical replay returns `already-recorded`; changing the
body under the same ID fails. Request files should be outside the project working
tree, so they do not dirty a reviewed commit. Use structured file writes, not
shell interpolation of JSON containing user text.

Every request has `id`, `op`, and `actor` (`codex:SESSION` or
`claude-code:SESSION`). Actor labels are cooperation metadata, not authenticated
identities. The helper does not cryptographically attest which model ran it.

## Request examples

Claim from a named, clean task branch with the full base SHA. Scope paths are
literal files or directories, no globs; `.` reserves the project. Reserve generated
outputs and lockfiles too. The runtime supplies branch and workspace itself.

```json
{
  "id": "claim-T-001-a", "op": "claim", "actor": "codex:session-a",
  "task": "T-001", "base": "FULL_BASE_COMMIT_SHA",
  "goal": "Return a useful error for an empty search",
  "scope": ["src/search.py", "tests/test_search.py"],
  "acceptance": ["Empty query returns the documented validation error", "Nonempty searches retain current behavior"]
}
```

Submit after committing and sharing source, using the full HEAD SHA. Evidence
gives commands, exit codes, observed output and limitations. The helper rejects
out-of-scope paths, uncommitted changes and a base that is no longer an ancestor,
and never executes the evidence text.

```json
{
  "id": "submit-T-001-a", "op": "submit", "actor": "codex:session-a",
  "task": "T-001", "head": "FULL_HEAD_COMMIT_SHA",
  "summary": "Added empty-query validation; source branch gm/T-001 pushed",
  "evidence": "python -m unittest tests.test_search; exit 0; 8 tests passed at HEAD",
  "not_done": "External service integration unavailable locally",
  "next": "Claude Code: fetch gm/T-001, checkout this exact head in a review worktree, review acceptance criteria and diff"
}
```

Review from that clean head, using the other platform's **real** identity:

```json
{
  "id": "review-T-001-a", "op": "review", "actor": "claude-code:session-b",
  "task": "T-001", "head": "FULL_HEAD_COMMIT_SHA", "verdict": "pass",
  "evidence": "Re-ran eight tests; exit 0. Checked empty and whitespace inputs against acceptance criteria.",
  "limits": "External service unavailable; assessed local validation only."
}
```

Use `changes` for required corrections and log each finding as a notice. Write an
honest `none` in limits when everything relevant was verified; do not invent a gap
to satisfy a template. A `review` is itself a durable response to the handoff.

## Operations

Required fields below are in addition to id/op/actor.

| op | Fields | Rule |
| --- | --- | --- |
| claim | task, base, goal, scope[], acceptance[] | New ID, clean named branch, no active overlapping scope/workspace/branch |
| submit | task, head, summary, evidence, not_done, next | Current owner; clears previous review |
| review | task, head, verdict (pass/changes), evidence, limits | Other platform; exact submitted clean HEAD. Structured peer output must also name nonempty `inspected` paths, and a `changes` verdict must carry at least one finding: exiting zero is not a review |
| finish | task, head, integrated_commit, evidence | Owner; exact approved head, captured integration pass and matching actual target tree |
| cancel | task, evidence | Owner; preserves history and frees scope; never deletes source |
| transfer | task, to (actor), evidence | Owner relinquishes to same platform session; run from destination; verify old writer stopped; clears review |
| refresh-base | task, base, target, evidence | Owner, unsubmitted building task, claimed worktree; new base descends from the old one, sits on the target, and is already an ancestor of task HEAD; scope revalidated |
| notice | task (ID or *), to (platform or *), kind, severity, summary, evidence | Any actor; ID becomes notice ID |
| ack | notice, evidence | Recipient records understanding/action; does not resolve |
| dispute | notice, evidence | Recipient states objection; blocker stays blocking |
| resolve | notice, evidence | Original reporter verifies resolution |
| learn | scope, rule, evidence | Propose bounded project lesson; ID becomes lesson ID |
| confirm | lesson, evidence | Other platform verifies; maximum ten active lessons |
| retire | lesson, evidence | Other platform records why a lesson no longer applies; keeps history |

**A stale base is repairable; wrong acceptance is not.** After a transfer or target
movement a task keeps its original `base`, making everything integrated since read as
out-of-scope. `refresh-base` fixes exactly that: owner only, only while the task is
building and unsubmitted, and the new base must descend from the old one, be present on
the named target, and already be an ancestor of the task HEAD; the resulting diff is
revalidated against scope before an atomic write recording the prior base. So a writer
whose target moved updates the task branch to contain the new base first - refreshing
cannot pull work onto the branch. Acceptance and scope have no such operation, so when
those are wrong, `cancel` with evidence and re-claim at the current base.

A `COLLISION` always blocks the named task (or all tasks if `task: "*"`).
S0 = dangerous/major correctness loss; S1 = broken acceptance or contract;
S2 = nonblocking improvement; S3 = preference. S0/S1 block regardless of notice
kind. Acknowledged and disputed blockers still block. Unrelated tasks remain free.

```json
{
  "id": "notice-17", "op": "notice", "actor": "claude-code:session-b",
  "task": "T-001", "to": "codex", "kind": "DEFECT", "severity": "S1",
  "summary": "Whitespace-only input bypasses validation; normalize before validating",
  "evidence": "src/search.py:18; input '   ' reaches the backend; expected validation error"
}
```

Recipient: `ack` with a fix commit/reproduction or an intended action. Reporter:
re-run the reproduction and `resolve` with the result. Builder then submits a new
head. Disagreement does not silently waive a required fix. If reporter unavailable,
keep review pending or use explicitly authorized identity recovery; no fake ACKs.

## Consistency and enforcement boundaries

The ledger is `ledger.json` on a dedicated Git ref. A transaction reads current
state, validates every precondition, commits immutably and advances the ref
atomically: locally via `git update-ref NEW EXPECTED_OLD`, remotely via fast-forward
push to one shared branch, revalidating up to three times on contention. Never
force-push it, apply a stale snapshot, hand-edit `ledger.json`, or fall back
offline. Source worktrees and indexes are untouched. Use the same remote branch in
every clone; an outage fails closed, a lost response can be retried by ID, and
`status` resolves ambiguity before repeating anything. Pushing the task branch is
separate: do it before inviting remote review.

The helper enforces claims, lifecycle, identity labels, message resolution and
commit matching. It cannot stop edits made through other shell tools, judge test
adequacy, prevent forged actor labels, or make a ledger check atomic with a later
merge. CI, branch protections and one authorized integrator remain necessary where
enforcement must be strong; never broaden hooks or permissions silently. `finish`
verifies target membership and the tested tree, not deployment or CI success, and
captured runs establish execution while free text stays an attributed claim.

No daemon is bundled: active agents check at boundaries, dormant ones next session.
Demonstrate both source and ledger access before claiming live cross-platform
operation. A direct bridge can cut pickup latency, but the ledger remains the
recoverable source of coordination state.

## Durable learning

`learn` records scope, a checkable rule and evidence; `confirm` requires the other
platform and only active lessons guide future sessions; `retire` keeps the rule and
why it stopped applying. Default `status` omits closed records, so consult `--all`
only for relevant history. The ledger is project-scoped, not a global instruction or
credential store, and archiving a large one needs an explicit history-preserving
migration rather than silent pruning.

## Execution and learning extensions

See [execution.md](execution.md) for captured runs, peer adapters, integration,
recovery, hooks and MCP. Claims additionally accept `depends_on` (completed task
IDs), `contracts` (path → agreed Git blob SHA), `task_class` and `model`. Submit
accepts `evidence_runs` (captured passing IDs at the same HEAD).

`measure` (completed task, escaped_defects, rework_rounds, evidence) and
`lesson-outcome` (lesson, task, result, evidence) record attributed observations,
not automatic performance scores; `metrics` returns them without promoting rules.
`remediate` (task, all current blocking notice IDs, in-scope paths, evidence) is
owner-only from the claimed building worktree and leaves approval blocked until
independent resolution.

Capture, integration and `peer-complete` are runtime-only: ordinary `apply` cannot
manufacture them by supplying report fields, and an invalid peer transaction
publishes nothing. Operator recovery requires its own explicit CLI flag and records
the authorization statement. These are cooperative controls, not a security
boundary against arbitrary code.
