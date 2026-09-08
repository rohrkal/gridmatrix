# Execution adapters (2.1.1)

## Contents

- Capability discovery and bounded peers
- Evidence and integration
- Recovery
- Hooks and MCP
- Limits and compatibility

## Capability discovery and bounded peers

`doctor` reports installed CLIs, versions and required flag availability, plus
coordination read access and installed-copy differences against the running skill.
`live_pair_ready` is false when a CLI is absent and null when execution is unverified.
Recent successful run records are shown separately as historical observations;
they do not certify current authentication or live availability.
Doctor never reads credential files or treats installation
as authentication. Both CLIs are optional; a successful actual run is the execution
probe. Missing tools leave a manual handoff and review pending.

```sh
python3 "$GM" doctor
python3 "$GM" peer --task T-001 --actor codex:SESSION --to claude-code \
  --kind review --id peer-001 --timeout 300 --max-turns 8 --max-dollars 2
python3 "$GM" peer --task T-002 --actor claude-code:SESSION --to codex \
  --adapter app-server --kind spec --id spec-002 --timeout 300
```

The coordinator must own the task. Review requires a submitted clean head; spec
review requires a building task with a written agreement. A disposable worktree
contains the exact source. The prompt contains the spec and scope without builder
rationale. The response schema requires verdict, findings, summary and limits.
A valid review creates notices and a review record under the actual invoked
platform's generated identity. A successful run with verdict `changes` still
requires fixes. A failed run never supplies approval.

Adapters:

- Claude: `claude -p` with JSON Schema, `Read,Grep,Glob` only, no configured MCP
  servers, `dontAsk` permission mode, maximum turns and USD budget.
- Codex exec: `codex -a never exec --sandbox read-only` with schema-constrained
  output and JSON events. Native usage/spend limits are not fabricated; wall time,
  output size and total run count are bounded.
- Codex App Server: initialize → thread/start → turn/start; stream events and
  capture the completed result. Additional permission/input requests fail the run.
  `--resume-run ID` resumes a recorded incomplete Codex App Server thread only for
  the same task/source head. This preserves platform session provenance.

One active peer run per task is enforced in the atomic ledger; default maximum
three starts per task (operator-selectable 1–10). `GRIDMATRIX_PEER_DEPTH` prevents
recursive Gridmatrix dispatch; child prompts prohibit other delegation too. This
is not a sandbox against arbitrary programs. Keep platform safeguards in effect.
Timeouts/output limits terminate the process tree. Every paid retry needs a new
run ID; replaying identical completed inputs returns the previous record.
An ambiguous/interrupted start requires inspection and explicit recovery first.

Model is optional: use an explicitly requested model, otherwise the platform's
configured default, recorded as unreported if the adapter cannot identify it.
Never infer actual model identity from platform name. CLI versions are captured.

## Evidence and integration

Write request/command files outside the source worktree. Example commands file:

```json
[["python3", "-m", "unittest", "discover", "-s", "tests"]]
```

Commands are argv arrays, executed directly without a shell. They are ordinary
programs, not sandboxed by Gridmatrix: inspect them and use existing authorization.
Do not pass secrets; redaction is best effort. Redacted logs stay in the local Git
common directory's `gridmatrix-runtime/RUN` folder. Ledger records carry hashes,
short tails, exit status and metadata; local paths are not remote artifact links.
Upload sanitized artifacts separately when the peer needs complete remote logs.

```sh
python3 "$GM" evidence --task T-001 --actor codex:SESSION \
  --id tests-001 --commands /tmp/checks.json --timeout 300
python3 "$GM" integrate --task T-001 --actor codex:SESSION \
  --id integration-001 --target refs/remotes/origin/main \
  --commands /tmp/checks.json --timeout 300
python3 "$GM" check --task T-001
```

`evidence` requires a clean committed source; source changes by a check invalidate
the result and are preserved. Attach captured IDs using `evidence_runs` on submit.
The helper verifies matching head and successful execution for those IDs.

`integrate` requires independent approval and a nonempty check list. Git 2.38+
provides merge-tree to construct the candidate without modifying the task branch.
Conflicts fail before execution. Checks run in an isolated worktree; modified
worktrees remain for inspection. Remote targets are fetched freshly. A target
change during or after testing invalidates the result. Candidate objects are kept
under `refs/gridmatrix/candidates/RUN`. They are local until explicitly shared.

After the authorized source merge, run finish from the approved task head:

```json
{"id":"finish-001","op":"finish","actor":"codex:SESSION","task":"T-001",
 "head":"FULL_REVIEWED_HEAD","integrated_commit":"FULL_ACTUAL_TARGET_COMMIT",
 "evidence":"Required CI passed; merge commit verified on target"}
```

The actual commit must occur on the target branch and match the tested candidate
tree exactly, supporting both merge and squash results. Changed conflict
resolutions need a new review/candidate. Gridmatrix does not configure repository
protections or silently enable auto-merge. A merge queue/required checks can close
the race between a local pre-merge check and the actual merge.

## Recovery

`apply --authorize-recovery request.json` is an explicit operator action. Only use
it with existing user authorization to recover the named task/notice/run. The flag
records that declaration; it is not independent authentication of a human decision.
Recovery is deliberately excluded from the MCP tools available to peers.

Task recovery: `op: recover`, task, expected_owner, to (new same-platform actor),
authorization (user request/decision reference), evidence (old writer stopped and
work preserved). Run from the clean named destination worktree. Approval is cleared;
builder history stays intact. Different-platform takeover needs a new task to
preserve contribution provenance and independent review.

Notice recovery: `op: recover`, notice, to (replacement verifier), authorization,
evidence. The verifier must be independent of the affected builder. The original
report remains unchanged and the blocker stays open until successor `resolve`.

Abandoned peer run: `op: recover-run`, run (original ID), actor (coordinator),
authorization, evidence that the process stopped. The run is recorded cancelled;
its attempt still counts toward the task budget. An explicitly recovered current
task owner may recover a predecessor run; both identities remain recorded. Never cancel a live process by
changing ledger state alone. No identity impersonation or automatic timer takeover.

## Hooks and MCP

`guard --task T --actor PLATFORM:SESSION PATH...` checks branch, workspace,
status, blockers and literal write scope. It performs no edit.

`hook --install` explicitly merges strict Claude hooks into project settings,
preserving other hooks. POSIX auto-install uses python3 on PATH. Windows users can
configure the same `hook` command in their supported shell. Set `GRIDMATRIX_ACTOR`
and `GRIDMATRIX_TASK` in the launched writer's environment. SessionStart injects
current state; PreToolUse denies unsupported/out-of-scope writes. Successful checks
defer to existing Claude permissions. Strict mode denies Bash/PowerShell because
arbitrary shell writes cannot be safely classified. Run approved checks via the
coordinator evidence command outside that restricted Claude session. This mode is
opt-in, not part of ordinary init. It does not intercept external filesystem edits.

`mcp --actor PLATFORM:SESSION` runs a stdio server using newline JSON-RPC.
Configure it in either platform with executable python3 and args:

```json
["/absolute/path/to/gridmatrix.py", "--repo", "/absolute/project", "mcp", "--actor", "codex:SESSION"]
```

Generate a fresh actor per launched session. Server configuration binds the actor;
request bodies cannot override it. Tools: read_inbox, claim_task, report_defect,
submit_review, transact (including scoped remediate). They call the same validated CLI. Runtime execution,
recovery, integration, ownership cancellation and permission configuration are
excluded. The local stdio boundary inherits the launcher identity and permissions;
it is not a remotely authenticated multi-user server.

## Limits and compatibility

Adapters are implemented against documented CLI/App Server contracts and tested
with controlled subprocess fixtures. Real CLI availability/authentication and
platform UI discovery must be exercised in the target environment. A fixture
returning a Claude/Codex-shaped response is never reported as a live model test.
Shared session labels and reports remain cooperative metadata, not cryptographic
model attestation. Use normal OS isolation and project protections.

References: [Codex exec](https://developers.openai.com/codex/non-interactive-mode),
[App Server](https://developers.openai.com/codex/app-server),
[Claude programmatic runs](https://code.claude.com/docs/en/headless),
[Claude hooks](https://code.claude.com/docs/en/hooks),
[MCP stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).

## Defect correction and interrupted completion

After a rejecting review, the owner can apply a `remediate` request:

```json
{"id":"fix-plan-001","op":"remediate","actor":"codex:SESSION","task":"T-001",
 "notices":["peer-001-finding-0"],"scope":["src/validation.py"],
 "evidence":"Correct the reported blank-input failure"}
```

Name every current blocking notice and a literal scope contained in the task scope.
Only task-specific DEFECT/ASSUMPTION blockers qualify; collisions and global
blockers still require resolution before writing. `guard` and strict hooks permit
only these scoped edits. A new blocker invalidates the plan until explicitly updated.
Commit the fix, then run `peer --kind verify` at the clean corrected head. The peer
receives the named findings and verifies all of them. Its passing completion resolves
them with its own identity and source SHA; it does not approve the whole task.
Submit and obtain ordinary independent review afterward. With manual review, the
original reporter or explicitly recovered verifier can resolve each notice with
verification evidence; never impersonate an unavailable automated reviewer.

Peer completion publishes findings, verdict and execution record in one atomic
ledger transaction. Interrupted publication leaves a local completion.json in the
run directory. Retry the identical peer command at the same source head to publish
that saved result without launching another model. Completed matching requests
return their previous result even after approval. Changed inputs fail; a new run
requires a new ID. If the source, ownership or task state changed, preserve the old
result and recover the obsolete run explicitly instead of applying it to new work.
Update both platform copies before using these operations.
