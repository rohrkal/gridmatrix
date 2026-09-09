# Execution adapters (2.2.0)

## Capability discovery and bounded peers

`doctor` reports installed CLIs, versions, required flags, coordination read access
and installed-copy differences against the running skill. `live_pair_ready` is false
when a CLI is absent and null when execution is unverified. Past run records are
history and certify nothing about current availability. Doctor never reads
credentials and never treats installation as authentication; only a successful run
probes execution. Missing tools leave a manual handoff.

```sh
python3 "$GM" doctor
python3 "$GM" peer --task T-001 --actor codex:SESSION --to claude-code \
  --kind review --id peer-001 --timeout 300 --max-turns 8 --max-dollars 2
python3 "$GM" peer --task T-002 --actor claude-code:SESSION --to codex \
  --adapter app-server --kind spec --id spec-002 --timeout 300
```

The coordinator must own the task; review needs a submitted clean head, spec review
a building task with a written agreement. The peer sees a disposable worktree and a
prompt carrying spec and scope without builder rationale. Its response must supply
verdict, findings, summary, limits and nonempty `inspected` evidence. A `changes`
verdict still requires fixes, and a failed run never supplies approval.

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

One active peer run per task, default maximum three starts (operator-selectable
1-10). `GRIDMATRIX_PEER_DEPTH` prevents recursive dispatch and child prompts
prohibit further delegation. This is not a sandbox: keep platform safeguards in
effect. Timeouts terminate the process tree, and a timed-out run that cannot release
its review worktree is reported failed rather than approved. Every paid retry needs
a new run ID; an interrupted start needs inspection and recovery first.

Model is optional: an explicitly requested one, else the platform default, recorded
as unreported when unidentifiable. Never infer model identity from platform name.

## Evidence and integration

Write request/command files outside the source worktree. Example commands file:

```json
[["python3", "-m", "unittest", "discover", "-s", "tests"]]
```

Commands are argv arrays run directly without a shell. They are ordinary programs,
not sandboxed by Gridmatrix, so inspect them and rely on existing authorization. Do
not pass secrets; redaction is best effort. Redacted logs stay in the local Git
common directory's `gridmatrix-runtime/RUN` folder, and ledger records carry hashes,
tails, exit status and metadata rather than remote artifact links - upload sanitized
artifacts separately when a peer needs full logs.

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

## Recovery, cold start and legacy repair

`apply --authorize-recovery request.json` is an explicit operator action; use it only
with existing user authorization for the named task, notice or run. The flag records
that declaration and is not independent authentication of a human decision. Recovery
is deliberately excluded from the MCP tools peers can reach.

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

`next --actor PLATFORM:SESSION` returns only what that identity can act on: open
notices addressed to it, tasks awaiting its review, verdicts on tasks it owns, approved
work awaiting its integration, and blocking notices it reported that a peer has
answered. Work owned by a *different* session of the same platform appears as
`inspect-owner-or-authorized-recovery` with the owning actor named, so a new session
can discover in-flight work. Visibility is not ownership: taking it still requires
explicit operator recovery.

`watch --actor PLATFORM:SESSION --timeout SECONDS` baselines current state and returns
only when something newly actionable appears or the timeout expires. It also watches the
integration target, because a peer advancing that branch is a Git event with no ledger
write. It waits without consuming model turns, so idle time costs no budget; never poll
by taking repeated agent turns.

`repair-ledger --actor PLATFORM:SESSION` repairs one historical defect only: a tree
whose single entry is `ledger.json` with a trailing carriage return, left by the
pre-fix Windows runtime. It validates the blob as a supported ledger before writing,
preserves parent history, publishes with an expected-old update or non-forced push,
reports `already-healthy` when there is nothing to do, and refuses every other
malformed shape rather than guessing.

## Hooks and MCP

`guard --task T --actor PLATFORM:SESSION PATH...` checks branch, workspace,
status, blockers and literal write scope. It performs no edit.

`hook --install` merges strict Claude hooks into project settings, preserving
others. **Auto-install refuses non-POSIX by design**, so Windows users configure the
same `hook` command manually in their shell. Set `GRIDMATRIX_ACTOR` and
`GRIDMATRIX_TASK` for the launched writer. SessionStart injects current state;
PreToolUse denies out-of-scope writes and defers otherwise to existing Claude
permissions. Strict mode denies Bash/PowerShell because arbitrary shell writes
cannot be classified; run approved checks through the evidence command outside that
session. Opt-in, not part of init, and it does not intercept external edits.

`mcp --actor PLATFORM:SESSION` runs a stdio server using newline JSON-RPC.
Configure it in either platform with executable python3 and args:

```json
["/absolute/path/to/gridmatrix.py", "--repo", "/absolute/project", "mcp", "--actor", "codex:SESSION"]
```

Generate a fresh actor per session; server configuration binds it and request
bodies cannot override it. Tools: read_inbox (actor-filtered, same as `next`),
claim_task, report_defect, submit_review, transact. Runtime execution, recovery,
integration, ownership cancellation and permission configuration are excluded. The
local stdio boundary inherits the launcher's identity and permissions; it is not a
remotely authenticated multi-user server.

## Limits and compatibility

Adapters are implemented against documented CLI/App Server contracts and tested
with controlled subprocess fixtures. Real CLI availability/authentication and
platform UI discovery must be exercised in the target environment. A fixture
returning a Claude/Codex-shaped response is never reported as a live model test.
Shared session labels and reports remain cooperative metadata, not cryptographic
model attestation. Use normal OS isolation and project protections.

**No peer adapter has been exercised as a live peer run.** A real `codex` executable
can exist on a maintainer machine and still be absent from the other platform's
`PATH`, where `doctor` then reports `missing-cli`: presence is not authentication,
and a test picking up a real binary through an inherited `PATH` is a
fixture-selection bug rather than live validation. Every adapter behaviour here is
verified by unit tests and code reading only.

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

Name every current blocking notice and a literal scope inside the task scope. Only
task-specific DEFECT/ASSUMPTION blockers qualify; collisions and global blockers must
be resolved first, and a new blocker invalidates the plan until updated. `guard` and
strict hooks permit only these scoped edits. Commit the fix, then run
`peer --kind verify` at the clean corrected head: the peer verifies all named
findings and its passing completion resolves them under its own identity and source
SHA, but does not approve the task, so submit for ordinary review afterward. Under
manual review the original reporter or an explicitly recovered verifier resolves each
notice with evidence; never impersonate an unavailable automated reviewer.

Peer completion publishes findings, verdict and execution record in one atomic
transaction. An interrupted publication leaves `completion.json` in the run
directory; retrying the identical command at the same source head publishes that
saved result without paying for another model run, and a completed matching request
replays its previous result even after approval. Changed inputs fail and need a new
ID. If source, ownership or task state changed, preserve the old result and recover
the obsolete run explicitly. Update both platform copies before using these.
