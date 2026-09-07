#!/bin/sh
# gridmatrix. Coordination protocol for Claude Code + Codex. POSIX sh, no deps.
#
#   gridmatrix.sh global                  install skills once, for every repo
#   gridmatrix.sh repo [path]             set up one repository
#   gridmatrix.sh repo [path] --vendor    also copy skills into the repo (teams/CI)
#   gridmatrix.sh update [path]           refresh upstream-owned files only
#   gridmatrix.sh update-all <paths...>   refresh many repos
#   gridmatrix.sh check [paths...]        report status, non-zero on problems
#   --dry-run works with any of the above
#
# Ownership, which is the whole design:
#   UPSTREAM-OWNED, overwritten on update: skills, .agents/gridmatrix.sh, and the
#       marked block inside AGENTS.md.
#   REPO-OWNED, never touched once created: everything else in .agents/, and
#       everything in AGENTS.md outside the markers.
#
# This script installs a copy of itself into each repo as .agents/gridmatrix.sh so CI
# can run `check` without the gridmatrix clone. That copy has no templates, so
# it supports check only.

VERSION="1.0.0"
KIT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TPL="$KIT/templates.md"
DRY=0; VENDOR=0; CMD=""; TARGETS=""

say() { echo "$@"; }
usage() { sed -n '3,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

# Extract one section of templates.md to stdout.
tpl() { awk -v want=">>>> FILE: $1" '
  $0 ~ /^>>>> FILE: / { on = ($0 == want); next }
  on { print }' "$TPL"; }

keep() {  # write only if absent: repo-owned
  if [ -f "$1" ]; then say "  keep   $1"
  elif [ "$DRY" = 1 ]; then say "  would create $1"
  else mkdir -p "$(dirname "$1")"; tpl "$2" > "$1"; say "  create $1"; fi
}

# ------------------------------------------------------------------ install

install_global() {
  say "Installing skills globally (gridmatrix $VERSION)"
  d_list="$HOME/.claude/skills $HOME/.agents/skills"
  [ -d "$HOME/.codex" ] && d_list="$d_list $HOME/.codex/skills"
  for d in $d_list; do
    for s in "$KIT"/skills/*/; do
      n=$(basename "$s")
      if [ "$DRY" = 1 ]; then say "  would sync $d/$n"
      else mkdir -p "$d"; rm -rf "$d/$n"; cp -R "$s" "$d/$n"; say "  sync   $d/$n"; fi
    done
    [ "$DRY" = 1 ] || echo "$VERSION" > "$d/.gridmatrix-version"
  done
  say ""
  say "Restart Claude Code and Codex so they pick up the skills directory."
}

merge_block() {
  if [ ! -f AGENTS.md ]; then
    [ "$DRY" = 1 ] && { say "  would create AGENTS.md"; return; }
    { tpl "AGENTS.head"; tpl "AGENTS.block"; } > AGENTS.md
    say "  create AGENTS.md"; return
  fi
  if grep -q '<!-- gridmatrix:begin' AGENTS.md; then
    [ "$DRY" = 1 ] && { say "  would replace managed block in AGENTS.md"; return; }
    tpl "AGENTS.block" > /tmp/_blk.$$
    awk -v bf=/tmp/_blk.$$ '
      /<!-- gridmatrix:begin/ { inb=1; while ((getline l < bf) > 0) print l; close(bf); next }
      /<!-- gridmatrix:end/   { inb=0; next }
      !inb { print }' AGENTS.md > AGENTS.md.tmp && mv AGENTS.md.tmp AGENTS.md
    rm -f /tmp/_blk.$$
    say "  update AGENTS.md block (surrounding content preserved)"
  else
    [ "$DRY" = 1 ] && { say "  would append managed block to AGENTS.md"; return; }
    printf '\n' >> AGENTS.md; tpl "AGENTS.block" >> AGENTS.md
    say "  append managed block to existing AGENTS.md"
  fi
}

ensure_claude_md() {
  [ -f CLAUDE.md ] || { keep CLAUDE.md "CLAUDE.md"; return; }
  if grep -q '^@AGENTS\.md' CLAUDE.md; then say "  keep   CLAUDE.md (imports AGENTS.md)"
  elif [ "$DRY" = 1 ]; then say "  would prepend @AGENTS.md to CLAUDE.md"
  else
    { head -n1 CLAUDE.md; echo; echo "@AGENTS.md"; tail -n +2 CLAUDE.md; } > CLAUDE.md.tmp
    mv CLAUDE.md.tmp CLAUDE.md
    say "  update CLAUDE.md (added @AGENTS.md, existing content kept)"
  fi
}

setup_repo() {
  [ -f "$TPL" ] || { echo "templates.md not found: run this from the gridmatrix clone, not the installed copy" >&2; exit 1; }
  cd "${1:-.}" || exit 1
  git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "not a git repo: ${1:-.}" >&2; return 1; }
  cd "$(git rev-parse --show-toplevel)" || exit 1
  say "Repo: $(pwd)"

  if [ "$DRY" = 1 ]; then say "  would sync .agents/gridmatrix.sh"
  else mkdir -p .agents; cp "$KIT/gridmatrix.sh" .agents/gridmatrix.sh; chmod +x .agents/gridmatrix.sh; say "  sync   .agents/gridmatrix.sh"; fi

  for f in STATE TASKS HANDOFF REVIEW DECISIONS FLAGS; do keep ".agents/$f.md" ".agents/$f.md"; done
  merge_block
  ensure_claude_md

  if [ "$VENDOR" = 1 ]; then
    for s in "$KIT"/skills/*/; do
      n=$(basename "$s")
      if [ "$DRY" = 1 ]; then say "  would vendor skill $n"
      else
        mkdir -p .agents/skills .claude/skills
        rm -rf ".agents/skills/$n" ".claude/skills/$n"
        cp -R "$s" ".agents/skills/$n"; cp -R "$s" ".claude/skills/$n"
        say "  vendor $n"
      fi
    done
  fi

  if [ "$DRY" = 1 ]; then say "  would stamp version $VERSION"
  else echo "$VERSION" > .agents/.gridmatrix-version; say "  version $VERSION"
    say ""; say "Next: run the gridmatrix-adopt skill, then: sh .agents/gridmatrix.sh check"; fi
}

# -------------------------------------------------------------------- check

check_one() {
  ( cd "${1:-.}" 2>/dev/null || exit 1
    cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
    fail=0; warn=0
    err() { echo "  FAIL: $1"; fail=$((fail+1)); }
    wrn() { echo "  WARN: $1"; warn=$((warn+1)); }

    have=$(cat .agents/.gridmatrix-version 2>/dev/null || echo none)
    printf '%s  gridmatrix=%s\n' "$(pwd)" "$have"
    [ -f .agents/TASKS.md ] || { echo "  FAIL: not adopted (run: gridmatrix.sh repo .)"; exit 1; }
    [ "$have" = "$VERSION" ] || wrn "stale install (upstream $VERSION)"

    for f in AGENTS.md CLAUDE.md .agents/STATE.md .agents/TASKS.md \
             .agents/HANDOFF.md .agents/REVIEW.md .agents/DECISIONS.md \
             .agents/FLAGS.md; do
      [ -f "$f" ] || err "missing $f"
    done

    grep -q '^@AGENTS\.md' CLAUDE.md 2>/dev/null || err "CLAUDE.md does not import AGENTS.md"

    b=$(grep -c '<!-- gridmatrix:begin' AGENTS.md 2>/dev/null); b=${b:-0}
    e=$(grep -c '<!-- gridmatrix:end'   AGENTS.md 2>/dev/null); e=${e:-0}
    [ "$b" -eq 0 ] && wrn "AGENTS.md has no managed block; updates will append"
    [ "$b" -gt 1 ] && err "AGENTS.md has $b managed blocks; remove all but one"
    [ "$b" -ne "$e" ] && err "managed block markers unbalanced (begin=$b end=$e)"

    grep -q PLACEHOLDER AGENTS.md 2>/dev/null && err "AGENTS.md has PLACEHOLDER (run gridmatrix-adopt)"
    grep -q PLACEHOLDER .agents/STATE.md 2>/dev/null && wrn "STATE.md has PLACEHOLDER"

    # context caps: oversized instruction files lose adherence
    for pair in AGENTS.md:200 .agents/STATE.md:120 .agents/TASKS.md:200 \
                .agents/HANDOFF.md:100 .agents/REVIEW.md:150 .agents/FLAGS.md:150; do
      p=${pair%:*}; c=${pair#*:}; [ -f "$p" ] || continue
      n=$(wc -l < "$p" | tr -d ' ')
      [ "$n" -gt "$c" ] && wrn "$p is $n lines (cap $c): summarize, do not append"
    done

    # Codex truncates merged instruction docs at project_doc_max_bytes silently
    bytes=$(find . -name AGENTS.md -not -path './node_modules/*' -exec cat {} + 2>/dev/null | wc -c | tr -d ' ')
    [ "${bytes:-0}" -gt 32768 ] && err "AGENTS.md tree is ${bytes}B, over Codex's 32 KiB default"

    # lock integrity
    awk '/^### T-/{id=$2;o="";s=""} /^- owner:/{o=$3} /^- status:/{s=$3
      gsub(/`/,"",o); gsub(/`/,"",s)
      if ((s=="building"||s=="auditing"||s=="resolving") && (o=="-"||o==""))
        print "  FAIL: task " id " is " s " with no owner (broken lock)"
    }' .agents/TASKS.md > /tmp/_t.$$ 2>/dev/null
    if [ -s /tmp/_t.$$ ]; then cat /tmp/_t.$$; fail=$((fail+1)); fi; rm -f /tmp/_t.$$

    # gate 6: an open flag blocks the recipient. Also the mechanical half of
    # collision detection, which does not depend on either agent self-reporting.
    if [ -f .agents/FLAGS.md ]; then
      o=$(grep -c '^- status: `open`' .agents/FLAGS.md 2>/dev/null); o=${o:-0}
      d=$(grep -c '^- status: `disputed`' .agents/FLAGS.md 2>/dev/null); d=${d:-0}
      c=$(awk '/^## F-/{t=$0} /^- status: `open`/{if (t ~ /COLLISION/) n++} END{print n+0}' .agents/FLAGS.md)
      [ "$c" -gt 0 ] && err "$c open COLLISION flag(s): stop work until resolved"
      [ "$o" -gt 0 ] && wrn "$o open flag(s) awaiting an answer (gate 6 blocks merge)"
      [ "$d" -gt 0 ] && wrn "$d disputed flag(s) waiting on the human"
    fi

    # more than one task in flight is legal only in separate worktrees
    inflight=$(grep -c '^- status: `\(building\|auditing\|resolving\)`' .agents/TASKS.md 2>/dev/null); inflight=${inflight:-0}
    if [ "$inflight" -gt 1 ]; then
      wt=$(git worktree list 2>/dev/null | wc -l | tr -d ' ')
      [ "${wt:-1}" -lt "$inflight" ] && err "$inflight tasks in flight but only ${wt:-1} worktree(s): agents will clobber each other"
    fi

    # the claim commit must touch TASKS.md alone, or the lock is not atomic
    staged=$(git diff --cached --name-only 2>/dev/null)
    if echo "$staged" | grep -q '^\.agents/TASKS\.md$'; then
      others=$(echo "$staged" | grep -cv '^\.agents/TASKS\.md$')
      [ "${others:-0}" -gt 0 ] && wrn "TASKS.md is staged with $others other file(s): a claim commit must be TASKS.md alone"
    fi

    # skills reachable, and valid frontmatter
    found=0
    for d in .agents/skills "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.codex/skills"; do
      [ -d "$d/gridmatrix-audit" ] && found=1
    done
    [ "$found" = 0 ] && wrn "no gridmatrix skills found: run gridmatrix.sh global"

    : > /tmp/_s.$$
    for f in $(find .agents/skills "$HOME/.claude/skills" -name SKILL.md 2>/dev/null | grep gridmatrix-); do
      grep -q '^name:' "$f"          || echo "  FAIL: $f missing 'name'" >> /tmp/_s.$$
      grep -q '^description:' "$f"   || echo "  FAIL: $f missing 'description'" >> /tmp/_s.$$
      grep -q '^argument-hint:' "$f" && echo "  FAIL: $f has argument-hint, not a valid SKILL.md key" >> /tmp/_s.$$
    done
    if [ -s /tmp/_s.$$ ]; then sort -u /tmp/_s.$$; fail=$((fail+1)); fi; rm -f /tmp/_s.$$

    if [ -d .agents/skills ] && [ -d .claude/skills ]; then
      for s in .agents/skills/*/; do n=$(basename "$s")
        diff -rq "$s" ".claude/skills/$n" >/dev/null 2>&1 || err "vendored skill $n drifted between .agents and .claude"
      done
    fi

    [ "$fail" -gt 0 ] && { echo "  $fail failure(s), $warn warning(s)"; exit 1; }
    echo "  ok ($warn warning(s))"; exit 0
  )
}

# ----------------------------------------------------------------- dispatch

[ $# -gt 0 ] || usage
while [ $# -gt 0 ]; do
  case "$1" in
    global|repo|update|update-all|check) [ -n "$CMD" ] || CMD="$1" ;;
    --vendor)  VENDOR=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) TARGETS="$TARGETS $1" ;;
  esac; shift
done
[ "$DRY" = 1 ] && say "DRY RUN, nothing will be written"

case "$CMD" in
  global) install_global ;;
  repo|update) t=$(echo "$TARGETS" | awk '{print $1}'); ( setup_repo "${t:-.}" ) ;;
  update-all)
    [ -n "$TARGETS" ] || { echo "update-all needs paths" >&2; exit 2; }
    for t in $TARGETS; do ( setup_repo "$t" ) || echo "FAILED: $t"; say ""; done ;;
  check)
    rc=0
    if [ -n "$TARGETS" ]; then for t in $TARGETS; do check_one "$t" || rc=1; done
    else check_one "." || rc=1; fi
    exit $rc ;;
  *) usage ;;
esac
