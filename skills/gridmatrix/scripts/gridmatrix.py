#!/usr/bin/env python3
"""Gridmatrix 2: dependency-free coordination with atomic Git ref transactions."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

VERSION = '2.2.0'
PLATFORMS = {'codex', 'claude-code'}
BEGIN, END = '<!-- gridmatrix:begin -->', '<!-- gridmatrix:end -->'
BLOCK = f'''{BEGIN}
## Gridmatrix coordination
Use the gridmatrix skill for coordinated project work. Read .gridmatrix/PROJECT.md
and run `python3 .agents/skills/gridmatrix/scripts/gridmatrix.py status` at session
start, after compaction, before each edit batch, and before handoff/integration.
Substitute `python` where no `python3` launcher exists: on a default Windows
install `python3` resolves to a Microsoft Store alias stub that exits without
running, so a command written with it silently does nothing.
Claim a task before editing; use one writer per task and separate working trees.
Immediately record material mistakes, overlap, and changed assumptions as notices;
acknowledge notices addressed to you. Pause affected work on unresolved blockers.
Reviews must come from the other platform and name the exact submitted commit.
Read confirmed project lessons; propose evidence-backed improvements after work.
Preserve existing instructions and user authorization. This protocol grants no
extra permissions. Never invent peer responses or claim a dormant agent was notified.
{END}
'''

class Error(Exception):
    pass

def require(ok, message):
    if not ok:
        raise Error(message)

def dumps(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'

def git(root, *args, data=None, check=True):
    try:
        # Byte-mode stdin: text mode rewrites LF to CRLF on Windows, which would
        # corrupt mktree entry names and any other newline-delimited Git input.
        p = subprocess.run(['git', '-C', str(root), *args],
                           input=None if data is None else data.encode('utf-8'),
                           capture_output=True, timeout=45,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
        p = subprocess.CompletedProcess(p.args, p.returncode,
                                        p.stdout.decode('utf-8', 'replace'),
                                        p.stderr.decode('utf-8', 'replace'))
    except subprocess.TimeoutExpired:
        raise Error('Git operation timed out; verify delivery by request ID before retrying') from None
    if check and p.returncode:
        raise Error(p.stderr.strip() or p.stdout.strip() or 'Git command failed')
    return p

def root_at(path):
    return Path(git(path, 'rev-parse', '--show-toplevel').stdout.strip()).resolve()

def empty():
    return {'schema': 3, 'tasks': {}, 'notices': {}, 'lessons': {}, 'receipts': {}, 'runs': {}}

def actor(value):
    require(isinstance(value, str) and re.fullmatch(r'(codex|claude-code):[A-Za-z0-9._-]+', value),
            'actor must be codex:SESSION or claude-code:SESSION')
    return value.split(':')[0]

def required(r, key):
    v = r.get(key)
    require(isinstance(v, str) and bool(v.strip()), f'{key} must be a nonempty string')
    return v

def scope_path(value):
    require(isinstance(value, str) and value and '\\' not in value, 'scope uses relative POSIX paths')
    p = PurePosixPath(value)
    require(not p.is_absolute() and '..' not in p.parts and not any(c in value for c in '*?['),
            'scope must be a literal relative file/directory, or .')
    require(not any(part.lower() == '.git' for part in p.parts), '.git is not task scope')
    return str(p).rstrip('/') or '.'

def overlaps(a, b):
    a, b = a.casefold(), b.casefold()
    return a == '.' or b == '.' or a == b or a.startswith(b + '/') or b.startswith(a + '/')

def blockers(state, task):
    return [n for n in state['notices'].values()
            if n['task'] in (task, '*') and n['blocking'] and n['status'] != 'resolved']

def remediation_allowed(state, task):
    plan = task.get('remediation') or {}
    active = blockers(state, task['id'])
    return bool(plan and active and
                {n['id'] for n in active} == set(plan['notices']) and
                all(n['task'] == task['id'] and n['kind'] in ('DEFECT', 'ASSUMPTION') for n in active))


def transition(state, r, context):
    """Validate one request against the latest state. Never trust a stale claim."""
    s = copy.deepcopy(state)
    require(s.get('schema') in (2, 3), 'unsupported ledger schema')
    who = required(r, 'actor'); platform = actor(who)
    rid = required(r, 'id')
    require(re.fullmatch(r'[A-Za-z0-9._-]{1,100}', rid), 'invalid request id')
    fingerprint = hashlib.sha256(dumps(r).encode()).hexdigest()
    if rid in s['receipts']:
        require(s['receipts'][rid]['hash'] == fingerprint, 'request id reused with different content')
        return s
    op = required(r, 'op')
    require(s['schema'] == 3 or op == 'upgrade', 'run upgrade before writing the v2 ledger')
    s.setdefault('runs', {})
    if op == 'upgrade':
        s['schema'] = 3
    elif op == 'remediate':
        t = s['tasks'].get(r.get('task'))
        require(t and t['owner'] == who and t['status'] == 'building', 'building task owner required')
        require(context['workspace'] == t['workspace'] and context['branch'] == t['branch'], 'use claimed worktree')
        notices = r.get('notices'); scope = r.get('scope')
        require(isinstance(notices, list) and notices and all(isinstance(n, str) for n in notices), 'name blocking notice IDs')
        require(isinstance(scope, list) and scope, 'name remediation scope')
        scope = [scope_path(p) for p in scope]
        require(all(any(parent == '.' or p == parent or p.startswith(parent + '/') for parent in t['scope']) for p in scope), 'remediation exceeds task scope')
        t['remediation'] = {'notices': notices, 'scope': scope, 'evidence': required(r, 'evidence')}
        require(remediation_allowed(s, t), 'remediation must cover current task defects; collisions and global blockers require resolution')
        t.update(review=None, integration=None)
    elif op == 'peer-complete':
        require(context.get('runtime_record'), 'peer completion requires the runtime')
        t = s['tasks'].get(r.get('task')); report = r.get('report')
        require(t and t['owner'] == who and isinstance(report, dict), 'invalid peer completion owner/report')
        start = s['runs'].get(rid + '-start')
        require(start and start['actor'] == who and start['task'] == t['id'] and rid not in s['runs'], 'missing or closed peer start')
        require(report.get('head') == start['head'], 'stale peer source')
        if report.get('passed'): require(start['head'] == context['head'], 'stale peer source')
        require(report.get('recipient') == start['recipient'], 'peer identity changed')
        require(report.get('plan_sha256') == start.get('plan_sha256'), 'peer inputs changed')
        if report.get('passed'):
            import gm_runtime
            value = gm_runtime.validate_review(report.get('result'), gm_runtime.api(globals()))
            peer = report['recipient']; require(actor(peer) != t['builder_platform'], 'independent peer required')
            purpose = report['purpose']
            require(t['status'] == ('review' if purpose == 'review' else 'building'), 'peer result is stale')
            if purpose == 'review': require(t['head'] == report['head'], 'peer result is stale')
            if purpose == 'verify':
                require(remediation_allowed(s, t) and report.get('remediation') == t['remediation'], 'remediation changed during verification')
                if value['verdict'] == 'pass':
                    for nid in t['remediation']['notices']:
                        n = s['notices'][nid]
                        n['responses'].append({'actor': peer, 'action': 'verify-remediation', 'head': report['head'], 'evidence': value['summary']})
                        n['status'] = 'resolved'
                    t['remediation'] = None
            else: require(not blockers(s, t['id']), 'new blockers invalidate peer completion')
            for i, f in enumerate(value['findings']):
                s = transition(s, {'id': rid + '-finding-' + str(i), 'op': 'notice', 'actor': peer,
                                  'task': t['id'], 'to': t['builder_platform'], 'kind': 'ASSUMPTION' if purpose == 'spec' else 'DEFECT',
                                  'severity': f['severity'], 'summary': f['problem'], 'evidence': f['location'] + ': ' + f['evidence']}, context)
            if purpose == 'review':
                s = transition(s, {'id': rid + '-review', 'op': 'review', 'actor': peer, 'task': t['id'],
                                  'head': report['head'], 'verdict': value['verdict'], 'evidence': value['summary'],
                                  'limits': value['limits'], 'model': report['model']}, context)
        s['runs'][rid] = dict(report, actor=who, task=t['id'])
    elif op == 'claim':
        tid = required(r, 'task')
        require(re.fullmatch(r'[A-Za-z0-9._-]{1,100}', tid), 'invalid task id')
        require(tid not in s['tasks'], 'task already exists; inspect its owner')
        require(not blockers(s, tid), 'unresolved blocking notice')
        scopes = r.get('scope')
        require(isinstance(scopes, list) and scopes, 'scope must be a nonempty list')
        scopes = [scope_path(x) for x in scopes]
        for t in s['tasks'].values():
            if t['status'] in ('done', 'cancelled'):
                continue
            require(not any(overlaps(a, b) for a in scopes for b in t['scope']),
                    f"scope overlaps {t['id']} owned by {t['owner']}")
            require(t['workspace'] != context['workspace'], f"workspace already claimed by {t['id']}")
            require(t['branch'] != context['branch'], f"branch already claimed by {t['id']}")
        acceptance = r.get('acceptance')
        require(isinstance(acceptance, list) and acceptance and all(isinstance(x, str) and x.strip() for x in acceptance),
                'acceptance must contain checkable criteria')
        dependencies = r.get('depends_on', [])
        require(isinstance(dependencies, list) and all(isinstance(x, str) for x in dependencies), 'invalid dependencies')
        for dep in dependencies:
            require(dep in s['tasks'] and s['tasks'][dep]['status'] == 'done', 'dependency is not done: ' + dep)
        contracts = r.get('contracts', {})
        require(isinstance(contracts, dict), 'contracts must map paths to Git blob SHAs')
        for path, digest in contracts.items():
            scope_path(path)
            require(isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{40,64}', digest), 'invalid contract SHA')
        base = required(r, 'base')
        s['tasks'][tid] = {'id': tid, 'owner': who, 'builder_platform': platform,
                          'scope': scopes, 'goal': required(r, 'goal'), 'acceptance': acceptance,
                          'base': base, 'branch': context['branch'], 'workspace': context['workspace'],
                          'status': 'building', 'head': None, 'review': None, 'handoff': None,
                          'depends_on': dependencies, 'contracts': contracts, 'integration': None,
                          'task_class': r.get('task_class', 'unspecified'), 'model': r.get('model', 'unknown'),
                          'review_rounds': 0}
    elif op == 'refresh-base':
        tid = required(r, 'task'); require(tid in s['tasks'], 'unknown task')
        t = s['tasks'][tid]
        require(who == t['owner'], 'only the task owner can refresh its base')
        require(t['status'] == 'building' and t.get('head') is None and
                t.get('review') is None and t.get('integration') is None,
                'refresh base only while the task is unsubmitted and building')
        require(context['workspace'] == t['workspace'] and context['branch'] == t['branch'],
                'refresh base from the claimed worktree and branch')
        base = required(r, 'base'); target = required(r, 'target')
        require(context.get('refresh_previous_base') == t['base'] and
                context.get('refresh_base') == base and context.get('refresh_target') == target and
                context.get('refresh_scope_verified'), 'refresh base requires validated Git ancestry and scope')
        require(base != t['base'], 'task already uses this base')
        t.setdefault('base_refreshes', []).append({
            'from': t['base'], 'to': base, 'target': target,
            'target_head': context['refresh_target_head'], 'evidence': required(r, 'evidence')})
        t['base'] = base
    elif op in ('submit', 'review', 'finish', 'cancel', 'transfer'):
        tid = required(r, 'task'); require(tid in s['tasks'], 'unknown task')
        t = s['tasks'][tid]
        if op == 'review':
            require(platform != t['builder_platform'], 'review requires the other platform')
            require(context['workspace'] != t['workspace'], 'review requires a separate worktree')
            require(t['status'] == 'review', 'task is not awaiting review')
            require(required(r, 'head') == t['head'] == context['head'], 'stale review: checkout submitted head')
            verdict = required(r, 'verdict')
            require(verdict in ('pass', 'changes'), 'verdict must be pass or changes')
            if verdict == 'pass':
                require(not blockers(s, tid), 'blocking notices must be resolved before approval')
            t['review_rounds'] = t.get('review_rounds', 0) + 1
            t['review'] = {'actor': who, 'head': t['head'], 'verdict': verdict,
                           'evidence': required(r, 'evidence'), 'limits': required(r, 'limits'),
                           'model': r.get('model', 'unknown')}
            t['status'] = 'approved' if verdict == 'pass' else 'building'
        else:
            require(who == t['owner'], 'only the task owner can perform this operation')
            require(t['status'] not in ('done', 'cancelled'), 'task is already closed')
            if op == 'submit':
                require(t['status'] in ('building', 'review', 'approved'), 'invalid submit state')
                require(not blockers(s, tid), 'resolve blocking notices before submission')
                require(required(r, 'head') == context['head'], 'submit must identify current HEAD')
                require(context['workspace'] == t['workspace'] and context['branch'] == t['branch'],
                        'submit from the claimed worktree and branch, or transfer first')
                t.update(status='review', head=r['head'], review=None, integration=None,
                         remediation=None, handoff={'summary': required(r, 'summary'), 'evidence': required(r, 'evidence'),
                                  'not_done': required(r, 'not_done'), 'next': required(r, 'next')})
            elif op == 'finish':
                require(t['status'] == 'approved', 'independent approval required')
                require(required(r, 'head') == t['head'] == context['head'], 'approval is stale')
                require(not blockers(s, tid), 'unresolved blocking notice')
                require(context.get('integration_verified'), 'verify actual integration before finish')
                require(t.get('integration') and t['integration']['head'] == t['head'], 'missing integration evidence')
                t.update(status='done', outcome=required(r, 'evidence'), integrated_commit=required(r, 'integrated_commit'))
            elif op == 'cancel':
                t.update(status='cancelled', outcome=required(r, 'evidence'))
            else:
                successor = required(r, 'to'); actor(successor)
                require(actor(successor) == t['builder_platform'],
                        'owner transfer preserves builder platform; split work for a different builder')
                t.update(owner=successor, workspace=context['workspace'], branch=context['branch'],
                         status='building', head=None, review=None, integration=None,
                         transfer_evidence=required(r, 'evidence'))
                for other in s['tasks'].values():
                    if other['id'] != tid and other['status'] not in ('done', 'cancelled'):
                        require(other['workspace'] != t['workspace'] and other['branch'] != t['branch'],
                                'destination workspace or branch is already claimed')
    elif op == 'notice':
        kind = required(r, 'kind')
        require(kind in ('COLLISION', 'DEFECT', 'ASSUMPTION', 'FRICTION', 'QUESTION'), 'invalid notice kind')
        to = required(r, 'to'); require(to in PLATFORMS or to == '*', 'to must be a platform or *')
        tid = required(r, 'task'); require(tid == '*' or tid in s['tasks'], 'unknown task')
        severity = required(r, 'severity'); require(severity in ('S0', 'S1', 'S2', 'S3'), 'invalid severity')
        s['notices'][rid] = {'id': rid, 'from': who, 'to': to, 'task': tid, 'kind': kind,
                             'severity': severity, 'blocking': kind == 'COLLISION' or severity in ('S0', 'S1'),
                             'summary': required(r, 'summary'), 'evidence': required(r, 'evidence'),
                             'status': 'open', 'responses': []}
    elif op in ('ack', 'resolve', 'dispute'):
        nid = required(r, 'notice'); require(nid in s['notices'], 'unknown notice')
        n = s['notices'][nid]; require(n['status'] != 'resolved', 'notice already resolved')
        if op == 'resolve':
            require(who == n.get('resolver', n['from']), 'assigned reporter/verifier must verify resolution')
        else:
            require(n['to'] in ('*', platform) and who != n['from'], 'only recipient may respond')
        n['responses'].append({'actor': who, 'action': op, 'evidence': required(r, 'evidence')})
        n['status'] = {'ack': 'acknowledged', 'resolve': 'resolved', 'dispute': 'disputed'}[op]
    elif op == 'recover-run':
        require(context.get('recovery_authorized'), 'recovery requires explicit operator authorization')
        run = required(r, 'run')
        require(run + '-start' in s['runs'] and run not in s['runs'], 'run is not abandoned/in-flight')
        start = s['runs'][run + '-start']
        task = s['tasks'].get(start['task'])
        require(start['actor'] == who or (task and task['owner'] == who and
                any(x['from'] == start['actor'] for x in task.get('recoveries', []))),
                'original coordinator or authorized recovered owner required')
        s['runs'][run] = {'kind': 'peer', 'passed': False, 'status': 'operator-cancelled', 'task': start['task'],
                          'actor': who, 'original_actor': start['actor'], 'authorization': required(r, 'authorization'), 'evidence': required(r, 'evidence')}
    elif op == 'recover':
        require(context.get('recovery_authorized'), 'recovery requires explicit operator authorization')
        reason = required(r, 'authorization')
        required(r, 'evidence')
        if 'notice' in r:
            n = s['notices'].get(r['notice']); require(n and n['status'] != 'resolved', 'notice is not open')
            successor = required(r, 'to'); actor(successor)
            t = s['tasks'].get(n['task'])
            require(not t or actor(successor) != t['builder_platform'], 'replacement verifier must be independent of builder')
            n['resolver'] = successor
            n['responses'].append({'actor': who, 'action': 'reassign-verifier', 'to': successor,
                                   'authorization': reason, 'evidence': r['evidence']})
        else:
            t = s['tasks'].get(r.get('task')); require(t and t['status'] not in ('done', 'cancelled'), 'task is not active')
            require(required(r, 'expected_owner') == t['owner'], 'owner changed; recovery is stale')
            successor = required(r, 'to'); actor(successor)
            require(actor(successor) == t['builder_platform'], 'recover to original builder platform; preserve authorship')
            require(context['branch'], 'recovery requires named destination branch')
            for other in s['tasks'].values():
                if other['id'] != t['id'] and other['status'] not in ('done', 'cancelled'):
                    require(other['workspace'] != context['workspace'] and other['branch'] != context['branch'], 'destination already claimed')
            t.setdefault('recoveries', []).append({'from': t['owner'], 'to': successor, 'authorization': reason, 'evidence': r['evidence']})
            t.update(owner=successor, workspace=context['workspace'], branch=context['branch'],
                     status='building', head=None, review=None, integration=None, remediation=None)
    elif op in ('capture', 'integration'):
        require(context.get('runtime_record'), 'use the evidence/integration runner to record execution')
        t = s['tasks'].get(r.get('task')); require(t, 'unknown task')
        require(t['owner'] == who or platform != t['builder_platform'], 'invalid evidence actor')
        report = r.get('report'); require(isinstance(report, dict), 'missing report')
        if report.get('kind') == 'peer-start':
            require(who == t['owner'], 'only task owner may start peer runs')
            starts = [(key, value) for key, value in s['runs'].items() if value.get('kind') == 'peer-start' and value.get('task') == t['id']]
            require(all(key[:-6] in s['runs'] for key, _ in starts), 'another peer run is active; inspect or recover it')
            require(type(report.get('max_runs')) is int and 1 <= report['max_runs'] <= 10, 'invalid run budget')
            require(len(starts) < report['max_runs'], 'peer run budget exhausted')
        if op == 'integration':
            require(who == t['owner'] and t['status'] == 'approved', 'approved task owner must validate integration')
            require(report.get('head') == t['head'] and report.get('passed'), 'integration checks did not pass at task head')
            require(not blockers(s, t['id']), 'unresolved blocking notice')
            t['integration'] = report
        s['runs'][rid] = dict(report, actor=who, task=t['id'])
    elif op == 'measure':
        t = s['tasks'].get(r.get('task')); require(t and t['status'] == 'done', 'measure a completed task')
        require(who == t['owner'] or platform != t['builder_platform'], 'invalid measurement actor')
        for key in ('escaped_defects', 'rework_rounds'):
            require(type(r.get(key)) is int and r[key] >= 0, 'metrics must be nonnegative integers')
        t.setdefault('measurements', []).append({'actor': who, 'escaped_defects': r['escaped_defects'],
                                                'rework_rounds': r['rework_rounds'], 'evidence': required(r, 'evidence')})
    elif op == 'lesson-outcome':
        lesson = s['lessons'].get(r.get('lesson')); require(lesson, 'unknown lesson')
        require(r.get('task') in s['tasks'], 'unknown task')
        require(r.get('result') in ('helped', 'recurred', 'not-applicable'), 'invalid lesson result')
        lesson.setdefault('outcomes', []).append({'actor': who, 'task': r['task'], 'result': r['result'], 'evidence': required(r, 'evidence')})
    elif op == 'learn':
        s['lessons'][rid] = {'id': rid, 'author': who, 'scope': scope_path(required(r, 'scope')),
                             'rule': required(r, 'rule'), 'evidence': required(r, 'evidence'),
                             'status': 'proposed', 'confirmation': None}
    elif op in ('confirm', 'retire'):
        lid = required(r, 'lesson'); require(lid in s['lessons'], 'unknown lesson')
        lesson = s['lessons'][lid]
        require(platform != actor(lesson['author']), 'other platform must validate lesson changes')
        if op == 'confirm':
            require(lesson['status'] == 'proposed', 'only proposed lessons can be confirmed')
            require(sum(x['status'] == 'active' for x in s['lessons'].values()) < 10,
                    'ten active lessons: retire or consolidate first')
        lesson.update(status='active' if op == 'confirm' else 'retired',
                      confirmation={'actor': who, 'evidence': required(r, 'evidence')})
    else:
        raise Error('unknown operation: ' + op)
    s['receipts'][rid] = {'hash': fingerprint, 'request': r,
                         'time': datetime.now(timezone.utc).isoformat()}
    return s

class Ledger:
    def __init__(self, root):
        self.root = root
        self.config = json.loads((root / '.gridmatrix/config.json').read_text(encoding='utf-8'))
        require(self.config.get('schema') in (2, 3), 'unsupported config schema')
        self.remote = self.config.get('remote')
        self.ref = 'refs/heads/' + self.config['branch'] if self.remote else 'refs/gridmatrix/state'
        git(root, 'check-ref-format', self.ref)
        if self.remote:
            require(self.remote in git(root, 'remote').stdout.splitlines(), 'configured remote is missing')

    def load(self):
        if not self.remote:
            p = git(self.root, 'rev-parse', '--verify', self.ref, check=False)
            head = p.stdout.strip() if not p.returncode else None
        else:
            p = git(self.root, 'ls-remote', '--exit-code', self.remote, self.ref, check=False)
            require(p.returncode in (0, 2), 'coordination remote unavailable; no offline ownership fallback')
            head = None
            if p.returncode == 0:
                # Unique ref prevents concurrent FETCH_HEAD or remote-tracking ref races.
                tempref = 'refs/gridmatrix/read/' + uuid.uuid4().hex
                try:
                    git(self.root, 'fetch', '--no-tags', '--no-write-fetch-head', self.remote,
                        self.ref + ':' + tempref)
                    head = git(self.root, 'rev-parse', tempref).stdout.strip()
                finally:
                    git(self.root, 'update-ref', '-d', tempref, check=False)
        if head is None:
            return None, empty()
        raw = git(self.root, 'show', head + ':ledger.json', check=False)
        require(raw.returncode == 0, 'coordination ref exists but is not a Gridmatrix ledger; do not overwrite it')
        state = json.loads(raw.stdout)
        require(state.get('schema') in (2, 3), 'unsupported ledger schema')
        return head, state

    def repair_legacy_cr_name(self, who):
        """Repair only the historical Windows ``ledger.json\r`` tree defect."""
        actor(who)
        tempref = None
        if not self.remote:
            p = git(self.root, 'rev-parse', '--verify', self.ref, check=False)
            head = p.stdout.strip() if not p.returncode else None
        else:
            p = git(self.root, 'ls-remote', '--exit-code', self.remote, self.ref, check=False)
            require(p.returncode in (0, 2), 'coordination remote unavailable; repair refused')
            head = p.stdout.split()[0] if p.returncode == 0 else None
            if head:
                tempref = 'refs/gridmatrix/repair/' + uuid.uuid4().hex
                git(self.root, 'fetch', '--no-tags', '--no-write-fetch-head', self.remote,
                    self.ref + ':' + tempref)
                fetched = git(self.root, 'rev-parse', tempref).stdout.strip()
                if fetched != head:
                    git(self.root, 'update-ref', '-d', tempref, check=False)
                    tempref = None
                    require(False, 'coordination ref changed during repair; retry from fresh state')
        require(head, 'coordination ref does not exist; nothing to repair')
        try:
            healthy = git(self.root, 'show', head + ':ledger.json', check=False)
            if healthy.returncode == 0:
                state = json.loads(healthy.stdout)
                self._validate_state_shape(state)
                return {'status': 'already-healthy', 'commit': head, 'ref': self.ref,
                        'transport': self.remote or 'local-only'}

            listing = git(self.root, 'ls-tree', '-z', head).stdout.split('\0')
            entries = [entry for entry in listing if entry]
            require(len(entries) == 1, 'repair refused: coordination tree is not the exact legacy one-entry shape')
            match = re.fullmatch(r'100644 blob ([0-9a-f]{40,64})\tledger\.json\r', entries[0])
            require(match, 'repair refused: expected the exact legacy ledger.json carriage-return entry')
            blob = match.group(1)
            raw = git(self.root, 'cat-file', 'blob', blob).stdout
            state = json.loads(raw)
            self._validate_state_shape(state)
            tree = git(self.root, 'mktree', data=f'100644 blob {blob}\tledger.json\n').stdout.strip()
            commit = git(self.root, '-c', 'user.name=Gridmatrix', '-c', 'user.email=gridmatrix@localhost',
                         'commit-tree', tree, '-p', head,
                         data=f'gridmatrix: repair legacy ledger filename ({who})\n').stdout.strip()
            if self.remote:
                result = git(self.root, 'push', '--porcelain', self.remote, commit + ':' + self.ref, check=False)
            else:
                result = git(self.root, 'update-ref', self.ref, commit, head, check=False)
            require(result.returncode == 0,
                    'coordination ref changed during repair; no force was used, retry from fresh state')
            return {'status': 'repaired', 'previous': head, 'commit': commit, 'ref': self.ref,
                    'transport': self.remote or 'local-only'}
        finally:
            if tempref:
                git(self.root, 'update-ref', '-d', tempref, check=False)

    @staticmethod
    def _validate_state_shape(state):
        require(isinstance(state, dict) and state.get('schema') in (2, 3),
                'repair refused: legacy blob is not a supported Gridmatrix ledger')
        required_maps = ('tasks', 'notices', 'lessons', 'receipts')
        require(all(isinstance(state.get(key), dict) for key in required_maps),
                'repair refused: legacy ledger shape is incomplete')
        if state['schema'] == 3:
            require(isinstance(state.get('runs'), dict),
                    'repair refused: schema 3 ledger is missing runs')

    def apply(self, request, context):
        for _ in range(3):
            parent, state = self.load()
            updated = transition(state, request, context)
            if updated == state:
                return {'id': request['id'], 'commit': parent, 'status': 'already-recorded'}
            blob = git(self.root, 'hash-object', '-w', '--stdin', data=dumps(updated)).stdout.strip()
            tree = git(self.root, 'mktree', data=f'100644 blob {blob}\tledger.json\n').stdout.strip()
            args = ['-c', 'user.name=Gridmatrix', '-c', 'user.email=gridmatrix@localhost',
                    'commit-tree', tree]
            if parent:
                args += ['-p', parent]
            commit = git(self.root, *args, data=f"gridmatrix: {request['op']} {request['id']}\n").stdout.strip()
            if self.remote:
                result = git(self.root, 'push', '--porcelain', self.remote, commit + ':' + self.ref, check=False)
            else:
                zero = '0' * len(commit)
                result = git(self.root, 'update-ref', self.ref, commit, parent or zero, check=False)
            if result.returncode == 0:
                return {'id': request['id'], 'commit': commit, 'status': 'recorded'}
            # Re-read/revalidate rather than force-push or blindly replay a stale snapshot.
        raise Error('coordination write failed after 3 attempts; inspect access/contention, do not edit unclaimed work')

def managed(old):
    b, e = old.count(BEGIN), old.count(END)
    require((b, e) in ((0, 0), (1, 1)), 'malformed Gridmatrix markers; preserve file and repair explicitly')
    if b:
        start, finish = old.index(BEGIN), old.index(END)
        require(start < finish, 'reversed Gridmatrix markers')
        return old[:start] + BLOCK.rstrip('\n') + old[finish + len(END):]
    return old + ('\n\n' if old and not old.endswith('\n\n') else '') + BLOCK

def safe_target(root, path):
    require(path.resolve().is_relative_to(root.resolve()), f'target escapes project: {path}')
    for p in [path, *path.parents]:
        if p == root.parent:
            break
        require(not p.is_symlink(), f'refusing symlink target: {p}')

def read_preserving(path):
    # newline='' keeps the file's own line endings, so rewriting an inherited
    # AGENTS.md edits the managed block and not every other line in the file.
    with open(path, encoding='utf-8', newline='') as f:
        return f.read()

def write_atomic(path, content):
    # Accepts bytes or str. Callers copying managed skill files must pass bytes so
    # the copy reproduces its source exactly, because check() and
    # installation_freshness() compare with read_bytes(); str is encoded as UTF-8
    # without newline translation, matching how these files are read back.
    if isinstance(content, str):
        content = content.encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.gridmatrix-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def install(root, remote, dry):
    source = Path(__file__).resolve().parents[1]
    configpath = root / '.gridmatrix/config.json'
    safe_target(root, configpath)
    existing = json.loads(configpath.read_text(encoding='utf-8')) if configpath.exists() else None
    if existing:
        require(existing.get('schema') in (2, 3), 'unsupported existing config; migration required')
        require(remote is None or remote == existing.get('remote'), 'transport change requires explicit ledger migration')
        config = dict(existing, schema=3, version=VERSION)
    else:
        config = {'schema': 3, 'version': VERSION, 'remote': remote, 'branch': 'gridmatrix-state'}
    if remote:
        require(remote in git(root, 'remote').stdout.splitlines(), 'remote does not exist')
    files = {configpath: dumps(config).encode('utf-8')}
    for name in ('AGENTS.md', 'CLAUDE.md'):
        p = root / name; safe_target(root, p)
        old = read_preserving(p) if p.exists() else ''
        if name == 'AGENTS.md':
            files[p] = managed(old).encode('utf-8')
        else:
            files[p] = (old if '@AGENTS.md' in old.splitlines() else '@AGENTS.md\n\n' + old).encode('utf-8')
    project = root / '.gridmatrix/PROJECT.md'
    if not project.exists():
        files[project] = '# Project agreement\n\nRecord the user objective, constraints, inherited instruction sources, verified commands\n(with date/result), baseline failures, and intended integration branch here.\nUnknown facts remain explicitly unknown; initialization does not verify the project.\n\n## Objective\nUnknown until adoption reads the user request.\n\n## Commands and baseline\nNot yet inspected.\n\n## Role calibration\nChoose builder by relevant project experience, tools and availability. The other\nplatform reviews. Record task class, outcomes, escaped defects and review rounds;\nuse comparable evidence, not permanent platform stereotypes.\n'.encode('utf-8')
    for dest in (root / '.agents/skills/gridmatrix', root / '.claude/skills/gridmatrix'):
        for src in source.rglob('*'):
            if src.is_file() and '__pycache__' not in src.parts and src.suffix != '.pyc':
                files[dest / src.relative_to(source)] = src.read_bytes()
    # Preflight every target before any write, including partially installed projects.
    for p in files:
        safe_target(root, p)
    for p, blob in files.items():
        if p.exists() and p.read_bytes() == blob:
            continue
        print(('would write ' if dry else 'write ') + str(p.relative_to(root)))
        if not dry:
            write_atomic(p, blob)
    print('transport: ' + ('remote ' + config['remote'] if config['remote'] else 'local worktrees only'))

def context_at(root):
    return {'head': git(root, 'rev-parse', '--verify', 'HEAD', check=False).stdout.strip() or None,
            'branch': git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False).stdout.strip(),
            'workspace': socket.gethostname() + ':' + str(root)}

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gm_runtime
    if gm_runtime.dispatch(argv, globals()):
        return
    p = argparse.ArgumentParser(description=__doc__, epilog='Execution commands: doctor, upgrade, evidence, peer, integrate, guard, metrics, next, watch, hook, mcp. Use COMMAND --help for options.')
    p.add_argument('--repo', default='.', help='project path (spaces supported)')
    sub = p.add_subparsers(dest='command', required=True)
    ini = sub.add_parser('init', help='install/update skill and preserve project instructions')
    ini.add_argument('--remote', help='shared Git remote name; omit for same-machine worktrees')
    ini.add_argument('--dry-run', action='store_true')
    sub.add_parser('session', help='generate a session suffix; does not launch an agent')
    status = sub.add_parser('status', help='refresh tasks, notices, and lessons')
    views = status.add_mutually_exclusive_group()
    views.add_argument('--all', action='store_true', help='include closed records, handoffs and receipt history')
    views.add_argument('--handoff', metavar='TASK', help='read builder rationale after independent diff review')
    apply = sub.add_parser('apply', help='atomically apply a JSON request file')
    apply.add_argument('file', help='JSON request file; - reads stdin')
    check = sub.add_parser('check', help='check installation or exact task approval; does not run project tests')
    check.add_argument('--task')
    repair = sub.add_parser('repair-ledger', help='repair only the legacy Windows ledger.json carriage-return defect')
    repair.add_argument('--actor', required=True)
    apply.add_argument('--authorize-recovery', action='store_true')
    args = p.parse_args(argv)
    if args.command == 'session':
        print(uuid.uuid4().hex[:16]); return
    root = root_at(args.repo)
    if args.command == 'init':
        install(root, args.remote, args.dry_run); return
    ledger = Ledger(root)
    if args.command == 'repair-ledger':
        print(dumps(ledger.repair_legacy_cr_name(args.actor)), end=''); return
    ctx = context_at(root)
    if args.command == 'apply':
        r = json.load(sys.stdin) if args.file == '-' else json.loads(Path(args.file).read_text(encoding='utf-8'))
        ctx['recovery_authorized'] = args.authorize_recovery
        _, current = ledger.load()
        if r.get('id') in current.get('receipts', {}):
            # A receipt is immutable. Let transition verify the exact fingerprint,
            # but do not let later worktree/preflight drift break safe retries.
            print(dumps(ledger.apply(r, ctx)), end=''); return
        gm_runtime.preflight(root, ledger, r, ctx, globals())
        if r.get('op') == 'claim':
            require(ctx['branch'], 'claim requires a named task branch')
            require(not git(root, 'status', '--porcelain').stdout, 'claim requires clean worktree; preserve existing changes')
            require(isinstance(r.get('base'), str), 'base is required')
            require(isinstance(r.get('scope'), list), 'scope must be a list')
            for item in r['scope']:
                safe_target(root, root / scope_path(item))
            resolved = git(root, 'rev-parse', '--verify', r['base'] + '^{commit}').stdout.strip()
            require(resolved == r['base'], 'base must be a full commit SHA')
            require(git(root, 'merge-base', '--is-ancestor', resolved, 'HEAD', check=False).returncode == 0,
                    'base must be an ancestor of task HEAD')
        if r.get('op') in ('submit', 'review', 'finish', 'transfer', 'recover', 'refresh-base'):
            require(not git(root, 'status', '--porcelain').stdout, 'commit/preserve changes before review operations')
        if r.get('op') == 'refresh-base':
            _, current = ledger.load()
            task = current['tasks'].get(r.get('task')); require(task, 'unknown task')
            require(task['owner'] == r.get('actor'), 'only the task owner can refresh its base')
            require(task['status'] == 'building' and task.get('head') is None and
                    task.get('review') is None and task.get('integration') is None,
                    'refresh base only while the task is unsubmitted and building')
            require(ctx['workspace'] == task['workspace'] and ctx['branch'] == task['branch'],
                    'refresh base from the claimed worktree and branch')
            base = required(r, 'base')
            resolved = git(root, 'rev-parse', '--verify', base + '^{commit}').stdout.strip()
            require(resolved == base, 'base must be a full commit SHA')
            require(git(root, 'merge-base', '--is-ancestor', task['base'], base,
                        check=False).returncode == 0,
                    'new base must descend from the previous base')
            require(git(root, 'merge-base', '--is-ancestor', base, 'HEAD',
                        check=False).returncode == 0,
                    'new base must be an ancestor of task HEAD')
            target = required(r, 'target')
            target_head = gm_runtime.target_head(root, target, gm_runtime.api(globals()))
            require(git(root, 'merge-base', '--is-ancestor', base, target_head,
                        check=False).returncode == 0,
                    'new base is not present on the named integration target')
            changed = git(root, 'diff', '--name-only', '-z', '--no-renames', base, 'HEAD').stdout.split('\0')
            for path in filter(None, changed):
                require(any(s == '.' or path == s or path.startswith(s + '/') for s in task['scope']),
                        'out-of-scope change after new base: ' + path)
            ctx.update(refresh_previous_base=task['base'], refresh_base=base, refresh_target=target,
                       refresh_target_head=target_head, refresh_scope_verified=True)
        if r.get('op') == 'submit':
            _, current = ledger.load()
            task = current['tasks'].get(r.get('task')); require(task, 'unknown task')
            require(git(root, 'merge-base', '--is-ancestor', task['base'], 'HEAD', check=False).returncode == 0,
                    'task HEAD no longer descends from agreed base')
            changed = git(root, 'diff', '--name-only', '-z', '--no-renames', task['base'], 'HEAD').stdout.split('\0')
            for path in filter(None, changed):
                require(any(s == '.' or path == s or path.startswith(s + '/') for s in task['scope']),
                        'out-of-scope change: ' + path)
        print(dumps(ledger.apply(r, ctx)), end=''); return
    head, state = ledger.load()
    if args.command == 'status':
        if args.handoff:
            t = state['tasks'].get(args.handoff); require(t, 'unknown task')
            state = {'task': args.handoff, 'head': t['head'], 'handoff': t['handoff']}
        elif not args.all:
            state = {k: {i: v for i, v in state[k].items() if v.get('status') not in ('done', 'cancelled', 'resolved', 'retired')}
                     for k in ('tasks', 'notices', 'lessons')}
            state['tasks'] = {i: {k: v for k, v in t.items() if k != 'handoff'}
                              for i, t in state['tasks'].items()}
        print(dumps({'transport': ledger.remote or 'local-only', 'ledger_commit': head, 'state': state}), end='')
    else:
        for name in ('AGENTS.md', 'CLAUDE.md', '.gridmatrix/PROJECT.md'):
            require((root / name).is_file(), 'missing ' + name)
        ag = (root / 'AGENTS.md').read_text(encoding='utf-8')
        require(ag.count(BEGIN) == ag.count(END) == 1 and ag.index(BEGIN) < ag.index(END), 'invalid managed block')
        require('@AGENTS.md' in (root / 'CLAUDE.md').read_text(encoding='utf-8').splitlines(), 'missing Claude import')
        first = root / '.agents/skills/gridmatrix'; second = root / '.claude/skills/gridmatrix'
        expected = {str(x.relative_to(first)) for x in first.rglob('*') if x.is_file() and '__pycache__' not in x.parts}
        actual = {str(x.relative_to(second)) for x in second.rglob('*') if x.is_file() and '__pycache__' not in x.parts}
        require('SKILL.md' in expected and expected == actual, 'skill copies missing or drifted')
        for f in expected:
            require((first / f).read_bytes() == (second / f).read_bytes(), 'skill copies drifted: ' + f)
        freshness = gm_runtime.installation_freshness(root)
        require(all(c['matches_running_skill'] for c in freshness['copies'].values()),
                'project skill copies differ from running skill; run init from the intended updated skill')
        if args.task:
            t = state['tasks'].get(args.task); require(t, 'unknown task')
            require(t['status'] in ('approved', 'done') and t['review'] and t['review']['verdict'] == 'pass',
                    'task lacks independent approval')
            require(t['head'] == ctx['head'] == t['review']['head'], 'approval is stale for current HEAD')
            require(not git(root, 'status', '--porcelain').stdout, 'dirty worktree invalidates check')
            require(not blockers(state, args.task), 'unresolved blocking notice')
            gm_runtime.verify_integration(root, t, globals())
        print('OK: ' + ('task approval matches HEAD; project CI remains required' if args.task else
                         'installation structure only; adoption and project tests are not certified'))

if __name__ == '__main__':
    try:
        main()
    except (Error, OSError, ValueError, KeyError, TypeError) as exc:
        print('gridmatrix: ' + str(exc), file=sys.stderr)
        sys.exit(1)
