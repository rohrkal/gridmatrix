# Developing Gridmatrix itself

`skills/gridmatrix/` is the canonical skill source in this repository. When this
repository adopts its own protocol, `init` also creates `.agents/skills/gridmatrix/`
and `.claude/skills/gridmatrix/`. Those are generated snapshots for discovery,
not additional places to author a fix. A personal installation is a separate
snapshot; updating repository files does not update that installation.

## Choose ownership and the running version

Read the shared ledger before editing. Give each writer a separate worktree and
claim literal paths. A change to the canonical skill normally needs ownership of
both generated skill directories too, because refreshing them is a write. A
reviewer or a writer with a documentation-only claim must leave those copies to
their owner. Split overlapping claims before starting a second implementation.

Use an explicit script path so the source being tested is unambiguous. The root
`gridmatrix.py` wrapper loads this checkout's canonical runtime. An invocation
from a personal installation or a generated copy can execute older code.
`doctor` compares installed copies with the running skill, not with GitHub or
another checkout. Two matching old snapshots do not establish freshness.

When changing the coordinator itself, keep ledger operations on a known-working,
schema-compatible runtime. Exercise new transaction behavior in disposable test
repositories first. Agree a runtime/schema switch with the other writer before
using it against the shared ledger; do not silently fall back to another ledger.

## Refresh at a deliberate boundary

Edit the canonical source, then review and refresh its generated snapshots before
committing the complete change for handoff. Run these commands from the owning
worktree; substitute `python3` if that is the available Python 3 interpreter:

```sh
python gridmatrix.py --repo . init --dry-run
python gridmatrix.py --repo . init
python gridmatrix.py --repo . check
```

Inspect the preview against the task scope. `init` can update root instructions
and configuration as well as skill copies; if those changes fall outside the
claim, agree ownership before running the write. Preserve project customizations
outside managed skill files and marked instruction blocks. Review the resulting
diff and stage only owned files.

`status` is a coordination read, not a synchronization step. Do not hide snapshot
updates inside routine reads or copy source changes into another writer's
worktree. A stale-copy report calls for an explicit refresh by the owner.

## Verify behavior and hand off the exact commit

For runtime changes, run focused regressions and the applicable existing suite:

```sh
python -m unittest discover -s tests -v
```

Choose assertions that exercise observable behavior: a ledger transaction must be
readable by the next operation; Unicode instructions must survive installation;
repeated initialization must preserve content. Include relevant platform cases
such as Windows line endings. Report skips, fixture limitations and baseline
failures separately from verified passes. Controlled peer fixtures do not prove
live model execution or authentication.

`check` establishes installation consistency, not behavioral correctness. After
committing owned source and snapshot changes, capture the appropriate checks with
`evidence`, submit that exact head, and have the other platform review it in a
separate worktree. Follow the existing integration gates before merging. See the
[execution reference](../skills/gridmatrix/references/execution.md) for request
formats and capture/integration commands.

A local snapshot refresh is not a release or a personal-skill update. State which
commit was reviewed, which target was integrated, and which installations were
actually updated.
