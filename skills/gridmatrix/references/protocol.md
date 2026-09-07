# Ledger protocol v2

## Commands

`python3 "$GM" --repo PATH init [--remote origin] [--dry-run]`
installs the project skill. `session` generates a session suffix. `status`
refreshes active tasks/notices/lessons without builder rationale. After independently
reading the spec and diff, use `status --handoff TASK` to retrieve that rationale.
`status --all` includes full history and handoffs; avoid it before independent review.
`apply request.json` (or `apply -` with JSON stdin) is the only write entrypoint.
`check` validates installation; `check --task T-001` additionally checks independent
approval against the current clean HEAD and outstanding blocking notices.

Use a unique stable `id` per request; retry the *same* body and ID after ambiguous
network failure. An identical replay returns `already-recorded`; changing the
body under the same ID fails. Request files should be outside the project working
tree, so they do not dirty a reviewed commit. Use structured file writes, not
shell interpolation of JSON containing user text.

Every request has `id`, `op`, and `actor` (`codex:SESSION` or
`claude-code:SESSION`). Actor labels are cooperation metadata, not authenticated
identities. The helper does not cryptographically attest which model ran it.

## Request examples

Claim from a named, clean task branch. Get the full base SHA from Git. Paths are
literal relative files/directories; `.` reserves the whole project. No globs.
Reserve generated outputs and dependency lockfiles too. The runtime captures
branch and hostname + resolved working directory; do not supply invented values.

```json
{
  "id": "claim-T-001-a", "op": "claim", "actor": "codex:session-a",
  "task": "T-001", "base": "FULL_BASE_COMMIT_SHA",
  "goal": "Return a useful error for an empty search",
  "scope": ["src/search.py", "tests/test_search.py"],
  "acceptance": ["Empty query returns the documented validation error", "Nonempty searches retain current behavior"]
}
```

Submit after committing and sharing source. Use the full HEAD SHA, not a branch
name. Evidence includes commands, exit codes, observed output and limitations.
The helper rejects changed paths outside the claim, uncommitted changes and a
base that is no longer an ancestor. It never runs the evidence text as commands.

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

Use `changes` for required corrections and log each concrete finding as a notice.
Use an honest `none` in limitations when everything relevant was verified; do
not invent a gap to satisfy a template. A `review` transaction is itself a durable
response to the submitted handoff.

## Operations

Required fields below are in addition to id/op/actor.

| op | Fields | Rule |
| --- | --- | --- |
| claim | task, base, goal, scope[], acceptance[] | New ID, clean named branch, no active overlapping scope/workspace/branch |
| submit | task, head, summary, evidence, not_done, next | Current owner; clears previous review |
| review | task, head, verdict (pass/changes), evidence, limits | Other platform; exact submitted clean HEAD |
| finish | task, head, evidence | Owner; exact approved clean HEAD; no blockers; record integration/acceptance evidence |
| cancel | task, evidence | Owner; preserves history and frees scope; never deletes source |
| transfer | task, to (actor), evidence | Owner relinquishes to same platform session; run from destination; verify old writer stopped; clears review |
| notice | task (ID or *), to (platform or *), kind, severity, summary, evidence | Any actor; ID becomes notice ID |
| ack | notice, evidence | Recipient records understanding/action; does not resolve |
| dispute | notice, evidence | Recipient states objection; blocker stays blocking |
| resolve | notice, evidence | Original reporter verifies resolution |
| learn | scope, rule, evidence | Propose bounded project lesson; ID becomes lesson ID |
| confirm | lesson, evidence | Other platform verifies; maximum ten active lessons |
| retire | lesson, evidence | Other platform records why a lesson no longer applies; keeps history |

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

The ledger lives in `ledger.json` on a dedicated Git ref. Transactions read the
latest state, validate all preconditions, create an immutable commit and atomically
advance the ref. Local mode uses `git update-ref NEW EXPECTED_OLD` across the shared
Git directory. Remote mode uses ordinary fast-forward pushes to one shared branch.
Competing writes re-read and revalidate up to three times. Never force-push this
branch, apply stale snapshots, edit ledger.json manually, or fall back offline.
The source worktree/index is untouched by these transactions.

Use the same configured remote branch across all clones. A remote outage fails
closed. Lost successful responses can be retried by ID. Inspect `status` when
failure is ambiguous before repeating other actions. Source commit transfer is
separate: push the task branch before inviting remote review.

The helper mechanically enforces cooperative claims, lifecycle, identity labels,
message resolution and commit matching. It cannot stop an agent from using other
shell tools to edit files, attest tests were executed, prevent forged actor labels,
or provide atomicity between a ledger check and a later source merge. Project CI,
branch protections and an authorized single integrator remain necessary where
strong enforcement is required. Do not install or broaden hooks/permissions
silently. `finish` is a coordination record, not proof of deployment or merge.

No daemon is bundled. Active agents check at boundaries; dormant agents read next
session. Both source and ledger access must be demonstrated before claiming live
cross-platform operation. A direct platform bridge can reduce pickup latency,
but the ledger remains the recoverable source of coordination state.

## Durable learning

`learn` records scope, a checkable rule and concrete evidence (notice/task IDs,
reproductions, successful techniques). `confirm` requires the other platform;
only active lessons guide future sessions. `retire` preserves the earlier rule
and the reason it stopped applying. Git history and receipts retain provenance.
The default status omits closed records to reduce context; consult `--all` only
for relevant history. The ledger is intentionally project-scoped, not a global
instruction or credential store. A large project's archive/compaction needs an
explicit history-preserving migration; this version does not silently prune it.
