# Project agreement

Verified record for joint Claude Code and Codex work on this repository. Every field
below states a checked fact with its evidence, or names an unknown and why it is unknown.
Dates are absolute. Bundle documentation version: 2.2.0.

## Objective

Make the Gridmatrix bundle genuinely plug and play, and keep it free of bloat.

Plug and play means the NEXT project to adopt Gridmatrix must not repeat the repair work
done here. It does not mean convenience: on 2026-09-08, upstream `main` (1773a73) was
reproduced silently bricking a fresh Windows project. `init` exited 0, `check` failed with
a confusing message, the first `claim` reported `"status": "recorded"`, and the tree entry
was stored as `ledger.json
`. Every later read and write then failed with "coordination
ref exists but is not a Gridmatrix ledger; do not overwrite it", which instructs the user
not to repair it. One operation, then a dead ledger with no in-tool recovery.

No bloat means the bundle should be what two agents need to work as a team under a clear
ruleset, and no more. A ruleset neither agent can hold in working memory is not a clear
methodology.

## Constraints that actually shaped decisions

- **No peer adapter has ever been exercised as a live Gridmatrix peer run.** State this
  precisely, because a looser version of it was wrong: a real `codex` executable *does*
  exist on the maintainer machine (`~/.codex/.sandbox-bin/codex.exe`), and a Codex test
  run selected it. It is simply not on `PATH` in the Claude Code shell, where `doctor`
  reports `live_pair_ready: false`, `readiness: missing-cli`. Presence is not
  authentication and not a validated peer run. Peer dispatch, review-evidence and App
  Server behaviour remain verified by unit tests and code reading only, and
  `claude plugin validate --strict` has never run against the manifests.
- **The account is Claude Pro; budget is a real limit.** On 2026-09-08 a 52-agent audit
  workflow consumed 1.46M subagent tokens, hit the spend limit mid-run, and returned zero
  findings because 50 of 52 agents died. The same audit was then completed inline with
  `grep` and short scripts at negligible cost. Analysis is done inline by default.
- **Development machine:** Windows 11, Python 3.14.3, Git 2.54.0.windows.1, with
  `core.autocrlf=true`. That setting caused real defects, not hypothetical ones.
- **GitHub Actions has never executed.** The repository is unpublished, so the
  ubuntu/windows matrix added in T-006 remains an untested test.

## Inherited instruction sources

`AGENTS.md` managed block, `CLAUDE.md` (imports `@AGENTS.md`), and
`docs/skill-development.md` (canonical-source versus generated-snapshot ownership, T-002,
Codex-owned). Preserve all three; they were not authored by this collaboration alone.

## Commands and baseline

Verified 2026-09-08 on Windows 11 / Python 3.14.3 unless stated.

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests` at `main` 6236315 | Ran 54 tests, `OK (skipped=2)` |
| `python gridmatrix.py --repo . check` on a fresh adoption | `OK: installation structure only` |
| `integrate --task T-004` (integ-T004-001) | passed; candidate f3065e25, tree a63173ca |
| `integrate --task T-006` (integ-T006-001) | passed; candidate e0646794, tree 2e2d999f |

**The two skips are environment gates, not masked failures.**
`test_hooks_preserve_permissions_and_existing_settings` is `skipUnless(os.name == 'posix')`
because hook auto-install refuses non-POSIX by design;
`test_symlink_target_refused` raises `SkipTest` when the OS denies symlink creation.

**Baseline before this work**, recorded so the improvement is auditable rather than
asserted: at upstream 1773a73 on this machine the suite reported
`Ran 44 tests` / `FAILED (failures=29, errors=4)`. Four root causes were fixed across T-001
and T-004: text-mode stdin put a carriage return in the `mktree` entry name; reads used the
locale encoding while writes used UTF-8; the installer decoded text instead of copying
bytes; and test fixtures were extensionless shebang scripts invisible to `shutil.which`.

## Integration state

Integration branch is `main`. **Local `main` and the published repository differ, and that
distinction is deliberate here because the protocol does not model it:** a task recorded
`done` has been integrated locally, not released. Confirm `origin/main` before describing
any work as shipped. Publication is Codex-owned under user authorisation.

## Role calibration

Assign by demonstrated evidence from this project, not platform stereotype.

- **Codex:** runtime recovery and handoff (T-007), development documentation (T-002),
  integration-target advancement and publication.
- **Claude Code:** Windows portability (T-001, T-004), plugin packaging and CI (T-006),
  instruction text (T-008 and the reference batch).

Review outcomes so far: T-001 `changes` then fixed; T-005 `changes` on an S1 version pin
and an S2 manifest field, cancelled and re-claimed as T-006 because no operation can amend
acceptance criteria, then `pass`; T-007 `changes` on an actor-filtering gap, then `pass`.

Escaped defects, recorded accurately rather than flatteringly: Codex caught three Claude
Code errors — a one-step install claim that the documented flow does not provide, a
schema-validation claim where only JSON parsing had been done, and a storage argument that
measured committed lines rather than object cost. Claude Code caught one Codex gap, where
`next` compared the full actor including session suffix and so hid in-flight work from any
new session of the same platform. On this evidence the cross-platform review is doing real
work in both directions, and the builder's own confidence has been the weaker signal.
