# gridmatrix

Coordination protocol so Claude Code and Codex can work the same repositories
without colliding, and so each one's work gets reviewed by the other.

Eight files. Skills install once per machine; only per-project state lands in
each repo.

---

## The constraint

The two agents cannot talk to each other. No channel, no shared memory, no
shared context, and no memory between sessions. Both are invoked by you, usually
at different times.

So all coordination is **write-then-read through git and the filesystem**. An
agent does not send; it leaves an artifact for whoever reads next. Every design
choice follows from that.

---

## Install

```sh
git clone <your-remote>/gridmatrix.git ~/gridmatrix

sh ~/gridmatrix/gridmatrix.sh global   # once per machine: the five skills
cd ~/code/some-project
sh ~/gridmatrix/gridmatrix.sh repo .   # once per repo: 9 files
```

Add an alias so the fleet commands are short:

```sh
alias gm='sh ~/gridmatrix/gridmatrix.sh'
```

Then invoke the `gridmatrix-adopt` skill in either agent. It fills project
facts, verifies the real build and test commands by executing them, and
reconciles any
pre-existing `AGENTS.md` or `CLAUDE.md`. Finish with:

```sh
sh .agents/gridmatrix.sh check
```

---

## Layout

```
gridmatrix.sh   install, update, and check. Installs a copy of itself into
                every repo as .agents/gridmatrix.sh so CI can run check
                without this clone.
templates.md    every file the installer writes, in delimited sections. Edit
                here to change your house defaults for all future repos.
skills/         five SKILL.md files, one per directory. The standard requires
                a directory each; this is the only count that cannot collapse.
```

Per repo you get `AGENTS.md`, `CLAUDE.md`, and `.agents/` holding `STATE.md`,
`TASKS.md`, `HANDOFF.md`, `REVIEW.md`, `DECISIONS.md`, `FLAGS.md`,
`gridmatrix.sh`.

---

## Ownership

This is what makes updates safe across many repos.

**Upstream-owned**, replaced on `update`: the skills, `.agents/gridmatrix.sh`,
and the block between `<!-- gridmatrix:begin -->` and `<!-- gridmatrix:end -->`
inside `AGENTS.md`.

**Repo-owned**, never touched once created: everything else in `.agents/`, and
everything in `AGENTS.md` outside those markers.

Write your project's own rules outside the markers and updates will not disturb
them.

---

## Fleet operations

```sh
sh ~/gridmatrix/gridmatrix.sh check ~/code/*        # what is stale or broken
git -C ~/gridmatrix pull
sh ~/gridmatrix/gridmatrix.sh update-all ~/code/*   # bring everything current
sh ~/gridmatrix/gridmatrix.sh repo . --dry-run      # show changes, write nothing
```

`check` exits non-zero for unadopted repos, stale versions, and structural
faults. Suitable for CI.

Global skills live in your home directory, so a teammate cloning the repo does
not get them. For shared repos use `gridmatrix.sh repo . --vendor`, which copies
the skills into `.agents/skills/` and `.claude/skills/` so they travel with the
repository. `check` verifies the two vendored copies have not drifted apart.

---

## The five skills

| Skill                        | Fires when                                  |
| ---------------------------- | ------------------------------------------- |
| `gridmatrix-session-start`   | Starting or resuming work, after `/compact` |
| `gridmatrix-audit`           | Reviewing the **other** agent's change      |
| `gridmatrix-handoff`         | Ending a session or passing work over       |
| `gridmatrix-retro`           | Every ~5 merged tasks, to distil friction   |
| `gridmatrix-adopt`           | Setting up or repairing a repo              |

Names are prefixed because skills install into a shared global namespace, where
an unprefixed `audit` would be shadowed by, or shadow, anything else installed
under the same name. Claude Code resolves personal over project skills silently
when names collide, so the prefix is what keeps that from happening quietly.

Each guards on `.agents/TASKS.md` existing, so they stay quiet in repos that
never adopted the protocol. That matters because they are installed globally,
across every repo you open.

Invoke by name for determinism (`$gridmatrix-audit` in Codex, `/gridmatrix-audit` in
Claude Code). Both tools may also select them by description.

Frontmatter is deliberately only `name` and `description`: the two fields the
open standard requires and both tools honour. `argument-hint` is **not** valid
in a `SKILL.md` and errors in Claude Code; `check` catches it if it reappears.

---

## Why the rules live in AGENTS.md and the procedures live in skills

Skills use progressive disclosure: the agent sees only a name and description,
and loads the body when it decides the skill applies. That is right for a long
procedure needed at one specific moment.

It is wrong for coordination invariants. If the agent does not invoke the skill,
there is no coordination, and the failure is silent. So the session-start read,
the single-writer rule, the gates, and the evidence rules sit in `AGENTS.md`,
which is always loaded.

---

## Telling each other about problems

Anything an agent notices outside its own task goes in `.agents/FLAGS.md`, typed
`COLLISION`, `DEFECT`, or `FRICTION`. Nothing said only in a reply reaches the
other agent, so an unlogged observation is a lost one.

An agent can always write "nothing to report," so the parts that matter are the
ones a machine checks rather than the ones an agent promises:

- An open `COLLISION` flag **fails** `check`. Work stops until it is answered.
- Any open flag warns, and gate 6 blocks merge until the recipient answers it
  `resolved` or `disputed`. `disputed` routes to you instead of blocking the
  other agent indefinitely.
- More tasks in flight than git worktrees **fails**, whether or not either agent
  noticed. This is the collision that actually destroys work, and it is visible
  in git without anyone self-reporting.
- Staging `TASKS.md` alongside other files warns, because a claim commit that
  carries extra files is not an atomic lock.

## Getting better at working together

Neither agent learns anything between sessions. No weights change, no context
carries over. What accumulates is written rules, and `gridmatrix-retro` is the
mechanism.

Every few tasks it reads the flag log and the audit history in git, groups
incidents by cause, and promotes anything that happened **three or more times**
into a one-line rule in the Conventions section of `AGENTS.md`. Because both
agents load that file every session, a lesson written once is applied from then
on without anyone remembering it.

Two constraints keep this from decaying into advice nobody reads:

- **Three occurrences minimum.** Two is a coincidence, and a rule written from
  it costs both agents context forever in exchange for nothing.
- **Ten rules maximum.** When Conventions is full, retro must merge or drop
  before it can add. A list that only grows stops being read, and an unread rule
  is worse than an absent one because it looks like coverage.

The strongest signal it looks for is the same audit finding recurring across
different tasks, because that means one agent reliably misses what the other
reliably catches. Retro also fills the calibration table in `DECISIONS.md`, and
after ten or more tasks may propose changing which platform builds and which
audits for a class of work. Below that it will tell you the sample is too small.

If a pattern is better enforced than requested, retro is instructed to say so
and recommend a hook, lint rule, or CI check rather than write a sentence.

## Two rules carrying most of the weight

**Whoever built a change does not audit it.** The value comes from a second
reader with no attachment to the plan, not from any claim about which model is
better. Roles alternate by task ID; the calibration table in `DECISIONS.md` is
where you replace that default with evidence from your own repos.

**Never run both agents in the same working directory.** They clobber each other
with no warning. Use `git worktree add` for parallel work.

---

## When it stops working, look here first

Ordered by how often each one is the cause.

1. Both agents in the same working directory. Everything else is downstream.
2. The auditor fixed something instead of reporting it. Separation gone.
3. The auditor read the builder's handoff before forming its own findings. That
   produces agreement, not review.
4. "Tests pass" with no pasted output. The most common false claim here.
5. Scope creep dressed as cleanup, making diffs unreviewable.
6. `STATE.md` grown past its cap, so nobody reads it, including the agents.
7. A decision being re-argued because nobody wrote it into `DECISIONS.md`.
8. An observation left in a reply instead of `FLAGS.md`, so it reached you and
   never reached the other agent.
9. Retro writing a rule from a single incident, until Conventions is ten lines
   of advice nobody follows.

---

## Known limits

- Instruction files are context, not enforcement. For irreversible operations
  (commits to `main`, force push, destructive shell) add a `PreToolUse` hook in
  `.claude/settings.json`. A markdown line is a request.
- `check` validates structure, not judgment. It cannot detect a rubber-stamp
  audit. The tell is a review whose "What I could NOT verify" section is empty.
- Codex truncates merged instruction docs at `project_doc_max_bytes`, 32 KiB by
  default, silently. `check` measures the `AGENTS.md` tree against it.
- The `~/.codex/skills` path is less clearly documented than the repo-level
  `.agents/skills`. The installer writes both. Verify with `/skills` in Codex.
