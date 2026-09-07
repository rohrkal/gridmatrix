# Gridmatrix review — 2026-09-07

Reviewed the original uploaded skill, installer, templates and four supporting
skills at `56b436f45665d602f28d36aa9446e9ee3b28e2db`. Reworked the kit as v2.0.0.

| Finding | Consequence | Change |
| --- | --- | --- |
| A claim commit on an arbitrary branch was described as a lock | Two task branches could independently claim the same work | One atomic coordination ref; competing writes re-read and revalidate |
| Global HANDOFF/REVIEW files were overwritten or cleared | Parallel handoffs could erase each other | Per-task records and immutable Git history |
| Handoff cleared owner while audits depended on builder identity | Review independence became ambiguous | Builder provenance persists through submission, review and completion |
| Disputed flags could stop blocking without resolution | A known serious defect could escape the gate | Acknowledgment/dispute retain blocking state; reporter verifies resolution |
| Reviews did not pin both source revisions | Approval could outlive the code reviewed | Full base/head SHA, exact clean-head checks, resubmission clears approval |
| The upload layout did not match documented installation paths | The documented root installer/skills paths were missing | One canonical skill plus a root Python entrypoint |
| Shell argument collection split paths at whitespace | Projects with spaces were mishandled | Structured argument parsing and subprocess argument arrays |
| Malformed managed markers could discard instruction text | Updating could truncate existing rules | Preflight marker/path validation, preservation and atomic file replacement |
| Session start always ended the turn; adoption broadly ran every command | Extra user round trips and potentially inappropriate commands | Continue authorized work; discover and run relevant project gates |
| Retro required three incidents and changed rules without peer confirmation | Serious first incidents were ignored; weak lessons could become permanent | Evidence-based proposals, peer confirmation and explicit retirement |
| Shared protocol relied on assumptions about platform behavior | False compatibility errors and overpromised communication | Official-doc checks, narrow portable metadata and explicit transport limits |

The original claim that `argument-hint` is invalid in **Claude Code** was too
broad: Claude Code supports it, while claude.ai/API packaging has a narrower
field set. Gridmatrix uses `name` and `description` for portability.
[Official Claude documentation](https://code.claude.com/docs/en/skills).

The original assertion that the agents categorically cannot talk directly was
also too broad. Direct integrations exist, but a skill alone does not provide
one. OpenAI currently directs Claude Code users to its Codex plugin/app server
rather than the deprecated MCP-server route. Gridmatrix remains usable through
a durable shared ledger without assuming that bridge is installed.
[Official OpenAI documentation](https://developers.openai.com/codex/mcp-server).

## Validation

Automated tests cover real Git worktrees and separate clones sharing a bare
remote, simultaneous claims, message resolution, role separation, stale approval,
request replay, scope enforcement, greenfield installation, preserved Claude and
Codex instructions, idempotence, malformed markers, symlinks, network failure,
and the complete submit/review/finish lifecycle. Run the checked-in suite for the
current count and results. Skill frontmatter was separately validated.

An independent Codex session adopted a temporary Claude-first project, implemented
whitespace validation, demonstrated failing-then-passing regression checks and
left a source bundle plus handoff. It correctly retained the claim and refused
approval/completion when Claude Code was unavailable. Its feedback exposed
rationale leakage in the default status output; v2 now provides an explicit
`status --handoff TASK` view after independent diff review.

Not validated here: a live Claude Code session, platform UI discovery in the
user's local installations, hosted Git authentication on their machines, or
production branch-protection integration. Test actor labels simulate platforms;
they are not evidence that both real models executed the workflow.

## Deliberate limits

No background agent launcher, automatic stale-owner takeover, unreviewed lesson
promotion, or permission bypass. Remote outage fails closed. Local mode is for
one repository's worktrees only. Coordination history is retained; very large
ledgers require an explicit history-preserving migration rather than silent
pruning. The helper does not enforce source writes made outside its commands.
