import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_gridmatrix import SCRIPT, cli, run, repo, claim, gm, write_fixture_cli

sys.path.insert(0, str(SCRIPT.parent))
import gm_runtime as rt

# Controlled protocol fixtures; these are not live Claude or Codex sessions.
FAKE = r'''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
if '--version' in sys.argv:
 print('gridmatrix-test-fixture 1.0'); sys.exit(0)
if '--help' in sys.argv:
 print('--output-schema --sandbox --output-last-message --json-schema --output-format --tools --max-turns --max-budget-usd --strict-mcp-config'); sys.exit(0)
mode=os.environ.get('GM_FIXTURE_MODE','pass')
result={'verdict':'pass','findings':[],'summary':'Fixture inspected source','limits':'Synthetic fixture; no live model','inspected':['app.py and submitted diff']}
if mode=='changes':
 result.update(verdict='changes',findings=[dict(severity='S1',location='app.py:1',problem='Fixture defect',evidence='Controlled reproduction')])
if mode=='changes-empty': result.update(verdict='changes',findings=[])
if mode=='no-inspection': result.pop('inspected')
if mode=='bad-json': result={'unexpected':True}
if mode=='failure': sys.exit(7)
if mode=='timeout': time.sleep(30)
if 'app-server' in sys.argv:
 for line in sys.stdin:
  msg=json.loads(line); method=msg.get('method')
  if method=='initialize': payload={'id':msg['id'],'result':{}}
  elif method in ('thread/start','thread/resume'):
   assert msg['params']['approvalPolicy']=='never'
   assert msg['params']['sandbox']=='read-only'
   payload={'id':msg['id'],'result':{'thread':{'id':'thread-fixture'}}}
  elif method=='turn/start':
   print(json.dumps({'id':msg['id'],'result':{'turn':{'id':'turn-fixture'}}}),flush=True)
   if mode=='approval':
    print(json.dumps({'id':900,'method':'item/commandExecution/requestApproval','params':{}}),flush=True); continue
   print(json.dumps({'method':'item/completed','params':{'item':{'type':'agentMessage','text':json.dumps(result)}}}),flush=True)
   print(json.dumps({'method':'turn/completed','params':{'turn':{'status':'completed'}}}),flush=True); continue
  else: continue
  print(json.dumps(payload),flush=True)
 sys.exit(0)
sys.stdin.read()
if '--output-last-message' in sys.argv:
 Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(result))
 print(json.dumps({'type':'thread.started','thread_id':'fixture'}))
else:
 assert sys.argv[sys.argv.index('--tools')+1]=='Read,Grep,Glob'
 assert '--strict-mcp-config' in sys.argv
 print(json.dumps({'type':'result','subtype':'success','is_error':False,'session_id':'fixture','structured_output':result,'usage':{}}))
'''

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = repo(self.base / 'project')
        cli(self.root, 'init')
        run(self.root, 'add', 'AGENTS.md', 'CLAUDE.md', '.agents', '.claude', '.gridmatrix')
        run(self.root, 'commit', '-m', 'adopt'); run(self.root, 'checkout', '-b', 'gm/task')
        self.head = run(self.root, 'rev-parse', 'HEAD')
        self.claim = claim(); self.claim['base'] = self.head
        self.apply(self.claim)
        self.commands = self.base / 'commands.json'
        self.commands.write_text(json.dumps([[sys.executable, '-c', 'print("checked")']]))
        self.bin = self.base / 'bin'; self.bin.mkdir()
        for name in ['codex', 'claude']:
            write_fixture_cli(self.bin, name, FAKE)

    def apply(self, value, ok=True, authorize=False):
        return cli(self.root, 'apply', *(['--authorize-recovery'] if authorize else []), '-', data=json.dumps(value), ok=ok)

    def env_cli(self, *args, ok=True, data=None):
        # Pass an explicit environment: managed test hosts may sanitize inherited
        # PATH changes while preserving an explicitly supplied subprocess env.
        p = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(self.root), *args],
                           input=data, text=True, capture_output=True, env=dict(os.environ))
        if ok and p.returncode:
            raise AssertionError(p.stderr)
        return p

    def submit(self):
        self.apply(dict(id='submit', op='submit', actor='codex:a', task='T1', head=self.head,
                        summary='submitted', evidence='baseline', not_done='none', next='review'))

    def peer(self, rid='peer1', mode='pass', to='claude-code', adapter='exec', timeout=5):
        env = {'PATH': str(self.bin) + os.pathsep + os.environ['PATH'], 'GM_FIXTURE_MODE': mode}
        with patch.dict(os.environ, env):
            return self.env_cli('peer', '--task', 'T1', '--actor', 'codex:a', '--to', to,
                                '--adapter', adapter, '--id', rid, '--timeout', str(timeout), ok=False)

    def state(self):
        return gm.Ledger(self.root).load()[1]

    def move_task_onto_new_base(self, out_of_scope=False):
        run(self.root, 'checkout', 'main')
        (self.root / 'base.txt').write_text('integrated dependency\n')
        run(self.root, 'add', 'base.txt'); run(self.root, 'commit', '-m', 'advance integration target')
        new_base = run(self.root, 'rev-parse', 'HEAD')
        run(self.root, 'checkout', 'gm/task'); run(self.root, 'merge', '--ff-only', 'main')
        (self.root / 'app.py').write_text('answer = 43\n')
        run(self.root, 'add', 'app.py')
        if out_of_scope:
            (self.root / 'outside.py').write_text('unexpected = True\n')
            run(self.root, 'add', 'outside.py')
        run(self.root, 'commit', '-m', 'task change')
        self.head = run(self.root, 'rev-parse', 'HEAD')
        return new_base

    def refresh_base(self, rid, base, actor='codex:a', ok=True):
        return self.apply(dict(id=rid, op='refresh-base', actor=actor, task='T1',
                               base=base, target='refs/heads/main',
                               evidence='Task moved onto the current integration target'), ok=ok)

    def test_refresh_base_preserves_provenance_and_allows_submit(self):
        old_base = self.state()['tasks']['T1']['base']
        new_base = self.move_task_onto_new_base()
        self.refresh_base('refresh', new_base)
        task = self.state()['tasks']['T1']
        self.assertEqual(task['base'], new_base)
        self.assertEqual(task['base_refreshes'], [{
            'from': old_base, 'to': new_base, 'target': 'refs/heads/main',
            'target_head': new_base,
            'evidence': 'Task moved onto the current integration target'}])
        self.submit()
        self.assertEqual(self.state()['tasks']['T1']['status'], 'review')

    def test_refresh_base_rejects_wrong_owner_target_and_scope(self):
        new_base = self.move_task_onto_new_base()
        self.assertIn('only the task owner', self.refresh_base(
            'wrong-owner', new_base, actor='claude-code:b', ok=False).stderr)
        self.assertIn('named integration target', self.refresh_base(
            'task-head-as-base', self.head, ok=False).stderr)

        # A fresh fixture is required because the out-of-scope path is committed.
        with tempfile.TemporaryDirectory() as folder:
            root = repo(Path(folder) / 'project')
            cli(root, 'init')
            run(root, 'add', 'AGENTS.md', 'CLAUDE.md', '.agents', '.claude', '.gridmatrix')
            run(root, 'commit', '-m', 'adopt'); run(root, 'checkout', '-b', 'gm/task')
            old = run(root, 'rev-parse', 'HEAD')
            request = claim(); request['base'] = old
            cli(root, 'apply', '-', data=json.dumps(request))
            run(root, 'checkout', 'main')
            (root / 'base.txt').write_text('integrated\n'); run(root, 'add', 'base.txt')
            run(root, 'commit', '-m', 'advance target'); base = run(root, 'rev-parse', 'HEAD')
            run(root, 'checkout', 'gm/task'); run(root, 'merge', '--ff-only', 'main')
            (root / 'outside.py').write_text('unexpected = True\n'); run(root, 'add', 'outside.py')
            run(root, 'commit', '-m', 'outside scope')
            refresh = dict(id='refresh', op='refresh-base', actor='codex:a', task='T1',
                           base=base, target='refs/heads/main', evidence='moved')
            result = cli(root, 'apply', '-', data=json.dumps(refresh), ok=False)
            self.assertIn('out-of-scope change after new base: outside.py', result.stderr)

    def test_refresh_base_rejects_backwards_or_submitted_task(self):
        old_base = self.state()['tasks']['T1']['base']
        new_base = self.move_task_onto_new_base()
        self.refresh_base('refresh', new_base)
        self.assertIn('descend from the previous base',
                      self.refresh_base('backwards', old_base, ok=False).stderr)
        self.submit()
        self.assertIn('unsubmitted and building',
                      self.refresh_base('after-submit', new_base, ok=False).stderr)

    def test_doctor_does_not_infer_authentication(self):
        with patch.dict(os.environ, {'PATH': str(self.bin) + os.pathsep + os.environ['PATH']}):
            d = json.loads(self.env_cli('doctor').stdout)
        self.assertTrue(d['platforms']['codex']['installed'])
        self.assertEqual(d['platforms']['codex']['authentication'], 'unverified')
        self.assertIsNone(d['live_pair_ready'])

    def test_capture_real_exit_code_and_replay(self):
        args = ['evidence', '--task', 'T1', '--actor', 'codex:a', '--id', 'check1', '--commands', str(self.commands)]
        result = json.loads(cli(self.root, *args).stdout)
        self.assertTrue(result['passed']); self.assertEqual(result['commands'][0]['exit_code'], 0)
        self.assertEqual(result, {k:v for k,v in json.loads(cli(self.root, *args).stdout).items() if k not in ('actor','task')})
        self.commands.write_text(json.dumps([[sys.executable, '-c', 'raise SystemExit(9)']]))
        self.assertNotEqual(cli(self.root, *args, ok=False).returncode, 0)
        args[args.index('check1')] = 'check2'
        failed = cli(self.root, *args, ok=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.state()['runs']['check2']['commands'][0]['exit_code'], 9)

    def test_mutating_check_fails_and_preserves_source(self):
        self.commands.write_text(json.dumps([[sys.executable, '-c', 'open("app.py","w").write("changed")']]))
        p = cli(self.root, 'evidence', '--task', 'T1', '--actor', 'codex:a', '--id', 'mutation', '--commands', str(self.commands), ok=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual((self.root / 'app.py').read_text(), 'changed')
        self.assertFalse(self.state()['runs']['mutation']['passed'])

    def test_peer_structured_success_records_real_adapter_provenance(self):
        self.submit(); p = self.peer()
        self.assertEqual(p.returncode, 0, p.stderr)
        t = self.state()['tasks']['T1']
        self.assertEqual(t['status'], 'approved')
        self.assertEqual(t['review']['actor'], 'claude-code:run-peer1')
        self.assertTrue(self.state()['runs']['peer1']['acknowledged'])

    def test_invalid_output_and_timeout_never_approve(self):
        self.submit()
        for rid, mode in [('bad', 'bad-json'), ('failed', 'failure'), ('timed', 'timeout')]:
            result = self.peer(rid, mode, timeout=1)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.state()['tasks']['T1']['status'], 'review')
            self.assertFalse(self.state()['runs'][rid]['passed'])
        self.assertIn('budget', self.peer('fourth').stderr)

    def test_peer_requires_inspection_and_actionable_changes(self):
        self.submit()
        for rid, mode in [('empty-changes', 'changes-empty'), ('blind-pass', 'no-inspection')]:
            result = self.peer(rid, mode)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.state()['tasks']['T1']['status'], 'review')
            runs = self.state()['runs']
            self.assertIn(rid, runs, result.stderr + repr(runs))
            self.assertFalse(runs[rid]['passed'])

    def test_next_filters_to_actionable_actor_work(self):
        self.assertEqual(json.loads(cli(self.root, 'next', '--actor', 'codex:a').stdout)['items'], [])
        cold = json.loads(cli(self.root, 'next', '--actor', 'codex:new-session').stdout)['items']
        self.assertEqual(cold[0]['action'], 'inspect-owner-or-authorized-recovery')
        self.assertEqual(cold[0]['owner'], 'codex:a')
        self.submit()
        reviewer = json.loads(cli(self.root, 'next', '--actor', 'claude-code:b').stdout)['items']
        self.assertEqual([(item['task'], item['action']) for item in reviewer], [('T1', 'review-exact-head')])
        self.assertEqual(json.loads(cli(self.root, 'next', '--actor', 'codex:a').stdout)['items'], [])
        self.apply(dict(id='question', op='notice', actor='claude-code:b', task='T1', to='codex',
                        kind='QUESTION', severity='S2', summary='Need owner input', evidence='Observed ambiguity'))
        owner = json.loads(cli(self.root, 'next', '--actor', 'codex:a').stdout)['items']
        self.assertEqual(owner[0]['key'], 'notice:question')
        self.apply(dict(id='reported-defect', op='notice', actor='codex:a', task='T1',
                        to='claude-code', kind='DEFECT', severity='S1', summary='Must verify fix',
                        evidence='Controlled defect'))
        self.apply(dict(id='author-ack', op='ack', actor='claude-code:b',
                        notice='reported-defect', evidence='Mechanical fix applied'))
        owner = json.loads(cli(self.root, 'next', '--actor', 'codex:a').stdout)['items']
        actions = {item['key']: item['action'] for item in owner}
        self.assertEqual(actions['verify-notice:reported-defect:acknowledged'],
                         'verify-or-resolve-reported-blocker')

    def test_watch_baselines_existing_and_wakes_for_new_review(self):
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), '--repo', str(self.root), 'watch', '--actor',
             'claude-code:b', '--timeout', '5', '--poll', '0.1'],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        import time
        time.sleep(0.25)
        self.submit()
        stdout, stderr = process.communicate(timeout=6)
        self.assertEqual(process.returncode, 0, stderr)
        result = json.loads(stdout)
        self.assertEqual(result['status'], 'actionable')
        self.assertEqual(result['items'][0]['action'], 'review-exact-head')

    def test_watch_wakes_when_integration_target_moves_to_tested_tree(self):
        (self.root / 'app.py').write_text('answer = 6 * 7\n')
        run(self.root, 'add', 'app.py'); run(self.root, 'commit', '-m', 'task change')
        self.head = run(self.root, 'rev-parse', 'HEAD')
        self.submit(); reviewed = self.peer()
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr + reviewed.stdout)
        cli(self.root, 'integrate', '--task', 'T1', '--actor', 'codex:a', '--id',
            'watch-integration', '--target', 'refs/heads/main', '--commands', str(self.commands))
        before = json.loads(cli(self.root, 'next', '--actor', 'codex:a').stdout)['items']
        self.assertEqual(before[0]['action'], 'advance-integration-target', repr(before))
        target = run(self.root, 'rev-parse', 'refs/heads/main')
        target_tree = run(self.root, 'rev-parse', 'refs/heads/main^{tree}')
        drift = gm.git(self.root, 'commit-tree', target_tree, '-p', target,
                       data='unrelated target drift\n').stdout.strip()
        run(self.root, 'update-ref', 'refs/heads/main', drift, target)
        drifted = json.loads(cli(self.root, 'next', '--actor', 'codex:a').stdout)['items']
        self.assertEqual(drifted[0]['action'], 'rerun-integration-candidate', repr(drifted))
        run(self.root, 'update-ref', 'refs/heads/main', target, drift)
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), '--repo', str(self.root), 'watch', '--actor',
             'codex:a', '--timeout', '5', '--poll', '0.1'],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        import time
        time.sleep(1.0)
        run(self.root, 'update-ref', 'refs/heads/main', self.head)
        after = json.loads(cli(self.root, 'next', '--actor', 'codex:a').stdout)['items']
        self.assertEqual(after[0]['action'], 'finish-integrated-task', repr(after))
        stdout, stderr = process.communicate(timeout=6)
        self.assertEqual(process.returncode, 0, stderr)
        result = json.loads(stdout)
        self.assertEqual(result['status'], 'actionable', repr(result))
        self.assertEqual(result['items'][0]['action'], 'finish-integrated-task')
        self.assertEqual(result['items'][0]['integrated_commit'], self.head)

    def test_peer_changes_create_blocking_notice(self):
        self.submit(); result = self.peer(mode='changes')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()['tasks']['T1']['status'], 'building')
        self.assertTrue(gm.blockers(self.state(), 'T1'))

    def test_recursive_peer_is_rejected(self):
        self.submit()
        with patch.dict(os.environ, {'GRIDMATRIX_PEER_DEPTH': '1'}):
            self.assertIn('recursive', self.peer().stderr)

    def test_peer_budget_is_atomic_and_recovery_retains_attempt(self):
        ledger = gm.Ledger(self.root); ctx = gm.context_at(self.root); ctx['runtime_record'] = True
        first = dict(id='orphan-start', op='capture', actor='codex:a', task='T1',
                     report=dict(kind='peer-start', max_runs=3, passed=False))
        ledger.apply(first, ctx)
        with self.assertRaises(gm.Error): ledger.apply(dict(first, id='second-start'), ctx)
        r = dict(id='recover', op='recover-run', actor='codex:a', run='orphan', authorization='User authorized recovery', evidence='Process stopped; source preserved')
        self.assertNotEqual(self.apply(r, ok=False).returncode, 0)
        self.apply(r, authorize=True)
        ledger.apply(dict(first, id='second-start'), ctx)
        self.assertEqual(self.state()['runs']['orphan']['status'], 'operator-cancelled')

    def test_independent_verifier_recovery_keeps_blocker_until_resolved(self):
        self.apply(dict(id='n1', op='notice', actor='claude-code:lost', task='T1', to='codex', kind='DEFECT', severity='S1', summary='bug', evidence='reproduction'))
        recovery = dict(id='recover', op='recover', actor='codex:a', notice='n1', to='claude-code:new', authorization='User directed replacement', evidence='Old session stopped')
        self.assertNotEqual(self.apply(recovery, ok=False).returncode, 0)
        self.apply(recovery, authorize=True)
        self.assertTrue(gm.blockers(self.state(), 'T1'))
        self.apply(dict(id='resolved', op='resolve', actor='claude-code:new', notice='n1', evidence='Reproduced passing fix'))
        self.assertFalse(gm.blockers(self.state(), 'T1'))
        self.assertEqual(self.state()['notices']['n1']['from'], 'claude-code:lost')

    def test_guard_rejects_outside_paths(self):
        cli(self.root, 'guard', '--task', 'T1', '--actor', 'codex:a', 'app.py')
        self.assertNotEqual(cli(self.root, 'guard', '--task', 'T1', '--actor', 'codex:a', 'other.py', ok=False).returncode, 0)

    @unittest.skipUnless(os.name == 'posix',
                         'hook --install deliberately refuses non-POSIX shells (gm_bridges.hooks); '
                         'the documented Windows path is manual configuration, so there is no '
                         'auto-install behaviour to assert here')
    def test_hooks_preserve_permissions_and_existing_settings(self):
        config = self.root / '.claude/settings.json'
        config.write_text(json.dumps({'permissions': {'deny': ['Read(secrets)']}, 'hooks': {'Stop': []}}))
        cli(self.root, 'hook', '--install'); first = config.read_text()
        cli(self.root, 'hook', '--install'); self.assertEqual(first, config.read_text())
        self.assertEqual(json.loads(first)['permissions']['deny'], ['Read(secrets)'])
        with patch.dict(os.environ, {'GRIDMATRIX_ACTOR':'codex:a','GRIDMATRIX_TASK':'T1'}):
            allowed = cli(self.root, 'hook', data=json.dumps({'hook_event_name':'PreToolUse','tool_name':'Edit','tool_input':{'file_path':str(self.root/'app.py')}}))
            self.assertEqual(json.loads(allowed.stdout), {})
            denied = cli(self.root, 'hook', data=json.dumps({'hook_event_name':'PreToolUse','tool_name':'Bash','tool_input':{'command':'touch app.py'}}))
            self.assertEqual(json.loads(denied.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_mcp_initialization_tools_and_identity_binding(self):
        messages = [dict(jsonrpc='2.0', id=1, method='initialize', params={'protocolVersion':'2025-06-18'}),
                    dict(jsonrpc='2.0', id=2, method='tools/list'),
                    dict(jsonrpc='2.0', id=3, method='tools/call', params={'name':'transact','arguments':{'request':dict(id='mcp-notice',op='notice',actor='claude-code:forged',task='T1',to='claude-code',kind='FRICTION',severity='S2',summary='latency',evidence='observed')}}),
                    dict(jsonrpc='2.0', id=4, method='tools/call', params={'name':'transact','arguments':{'request':dict(id='mcp-recovery',op='recover')}})]
        p = cli(self.root, 'mcp', '--actor', 'codex:a', data='\n'.join(json.dumps(x) for x in messages)+'\n')
        replies = [json.loads(x) for x in p.stdout.splitlines()]
        self.assertEqual(replies[0]['result']['protocolVersion'], '2025-06-18')
        self.assertEqual(len(replies[1]['result']['tools']), 5)
        self.assertFalse(replies[2]['result']['isError']); self.assertTrue(replies[3]['result']['isError'])
        self.assertEqual(self.state()['notices']['mcp-notice']['from'], 'codex:a')

    def test_schema_upgrade_preserves_records(self):
        ledger = gm.Ledger(self.root); parent, state = ledger.load(); state['schema'] = 2
        blob = run(self.root, 'hash-object', '-w', '--stdin') if False else gm.git(self.root, 'hash-object','-w','--stdin',data=gm.dumps(state)).stdout.strip()
        tree = gm.git(self.root,'mktree',data=f'100644 blob {blob}\tledger.json\n').stdout.strip()
        commit = gm.git(self.root,'commit-tree',tree,'-p',parent,data='old schema\n').stdout.strip()
        run(self.root,'update-ref',ledger.ref,commit,parent)
        cli(self.root,'upgrade','--actor','codex:a'); cli(self.root,'upgrade','--actor','claude-code:b')
        self.assertEqual(self.state()['schema'],3); self.assertIn('T1',self.state()['tasks'])

    def test_appserver_adapter_success_and_permission_block(self):
        # Separate task with Claude as original builder, to exercise the Codex adapter.
        self.apply(dict(id='cancel',op='cancel',actor='codex:a',task='T1',evidence='fixture complete'))
        r = claim('T2', 'claude-code:b'); r['base'] = self.head; self.apply(r)
        self.apply(dict(id='submit2',op='submit',actor='claude-code:b',task='T2',head=self.head,summary='ready',evidence='fixture',not_done='none',next='review'))
        args=['peer','--task','T2','--actor','claude-code:b','--to','codex','--adapter','app-server','--id','rpc1','--timeout','3']
        with patch.dict(os.environ, {'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],'GM_FIXTURE_MODE':'approval'}):
            result=self.env_cli(*args,ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.state()['tasks']['T2']['status'],'review')
        args[args.index('rpc1')]='rpc2'; args+=['--resume-run','rpc1']
        with patch.dict(os.environ, {'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],'GM_FIXTURE_MODE':'pass'}):
            result=self.env_cli(*args,ok=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.state()['tasks']['T2']['status'],'approved')

    def test_target_drift_invalidates_integration(self):
        self.submit(); self.peer()
        args=['integrate','--task','T1','--actor','codex:a','--id','int1','--target','refs/heads/main','--commands',str(self.commands)]
        cli(self.root,*args); cli(self.root,'check','--task','T1')
        tree=run(self.root,'rev-parse','HEAD^{tree}')
        new=gm.git(self.root,'commit-tree',tree,'-p',self.head,data='target advanced\n').stdout.strip()
        run(self.root,'update-ref','refs/heads/main',new)
        self.assertIn('target advanced',cli(self.root,'check','--task','T1',ok=False).stderr)

    def test_codex_exec_adapter(self):
        self.apply(dict(id='cancel', op='cancel', actor='codex:a', task='T1', evidence='fixture'))
        task = claim('T2', 'claude-code:b'); task['base'] = self.head; self.apply(task)
        self.apply(dict(id='submit2', op='submit', actor='claude-code:b', task='T2', head=self.head,
                        summary='ready', evidence='fixture', not_done='none', next='review'))
        with patch.dict(os.environ, {'PATH': str(self.bin) + os.pathsep + os.environ['PATH']}):
            result = self.env_cli('peer', '--task', 'T2', '--actor', 'claude-code:b', '--to', 'codex', '--id', 'exec1')
        self.assertEqual(self.state()['tasks']['T2']['review']['actor'], 'codex:run-exec1')

    def test_dependencies_and_contracts_fail_closed(self):
        ctx = gm.context_at(self.root)
        dep = dict(self.claim, id='dep-claim', task='T2', depends_on=['T1'], scope=['docs'])
        with self.assertRaisesRegex(gm.Error, 'dependency is not done'):
            rt.preflight(self.root, gm.Ledger(self.root), dep, ctx, gm.__dict__)
        contract = dict(self.claim, contracts={'app.py': '0' * 40})
        with self.assertRaisesRegex(gm.Error, 'shared contract changed'):
            rt.preflight(self.root, gm.Ledger(self.root), contract, ctx, gm.__dict__)
        contract['contracts']['app.py'] = run(self.root, 'rev-parse', 'HEAD:app.py')
        rt.preflight(self.root, gm.Ledger(self.root), contract, ctx, gm.__dict__)
        state = self.state(); state['tasks']['T1']['status'] = 'done'
        tree = run(self.root, 'rev-parse', 'HEAD^{tree}')
        state['tasks']['T1']['integrated_commit'] = gm.git(self.root, 'commit-tree', tree, data='unrelated dependency').stdout.strip()
        class Ledger:
            def load(self): return None, state
        with self.assertRaisesRegex(gm.Error, 'dependency source is not present'):
            rt.preflight(self.root, Ledger(), dep, ctx, gm.__dict__)

    def test_task_recovery_clears_approval_and_retains_provenance(self):
        self.submit(); self.peer()
        recovery = dict(id='takeover', op='recover', actor='codex:new', task='T1',
                        expected_owner='codex:a', to='codex:new', authorization='Operator continued task', evidence='Old writer stopped')
        self.assertNotEqual(self.apply(recovery, ok=False).returncode, 0)
        self.apply(recovery, authorize=True)
        task = self.state()['tasks']['T1']
        self.assertEqual(task['owner'], 'codex:new'); self.assertIsNone(task['review'])
        self.assertEqual(task['recoveries'][0]['from'], 'codex:a')
        self.assertEqual(task['builder_platform'], 'codex')

    def test_learning_measurements_keep_unknown_distinct_from_zero(self):
        self.assertEqual(json.loads(cli(self.root, 'metrics').stdout)['tasks'], [])
        self.apply(dict(id='lesson', op='learn', actor='codex:a', scope='app.py', rule='Check boundaries', evidence='incident'))
        self.apply(dict(id='outcome', op='lesson-outcome', actor='claude-code:b', lesson='lesson', task='T1', result='recurred', evidence='repeat incident'))
        self.assertEqual(self.state()['lessons']['lesson']['status'], 'proposed')
        self.assertEqual(json.loads(cli(self.root, 'metrics').stdout)['lesson_outcomes']['lesson'][0]['result'], 'recurred')
        with self.assertRaises(gm.Error):
            gm.transition(self.state(), dict(id='measure', op='measure', actor='codex:a', task='T1', escaped_defects=0, rework_rounds=0, evidence='incomplete'), gm.context_at(self.root))

    def test_appserver_stderr_only_is_bounded(self):
        import gm_appserver
        binary = write_fixture_cli(
            self.bin, 'noisy',
            '#!/usr/bin/env python3\nimport sys,time\nsys.stderr.write("x"*5000000);sys.stderr.flush();time.sleep(10)\n')
        folder = self.base / 'rpc-noise'; folder.mkdir()
        result = gm_appserver.execute(str(binary), self.root, folder, 'review', rt.REVIEW_SCHEMA, 2, dict(os.environ))
        self.assertEqual(result['status'], 'output-limit')
        self.assertLessEqual((folder / 'stderr.log').stat().st_size, 4 * 1024 * 1024)

    def test_completed_peer_replay_after_approval(self):
        self.submit(); first = self.peer('replay')
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.peer('replay')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.state()['tasks']['T1']['review_rounds'], 1)
        self.assertNotEqual(self.peer('replay', timeout=4).returncode, 0)

    def test_scoped_remediation_and_independent_verification(self):
        self.submit(); self.peer('bad', 'changes')
        self.assertNotEqual(cli(self.root,'guard','--task','T1','--actor','codex:a','app.py',ok=False).returncode,0)
        self.apply(dict(id='fix-plan',op='remediate',actor='codex:a',task='T1',notices=['bad-finding-0'],scope=['app.py'],evidence='Fix reported input case'))
        cli(self.root,'guard','--task','T1','--actor','codex:a','app.py')
        self.assertNotEqual(cli(self.root,'guard','--task','T1','--actor','codex:a','README.md',ok=False).returncode,0)
        self.assertTrue(gm.blockers(self.state(),'T1'))
        (self.root/'app.py').write_text('answer = 6 * 7\n')
        run(self.root,'add','app.py'); run(self.root,'commit','-m','scoped correction')
        self.head=run(self.root,'rev-parse','HEAD')
        with patch.dict(os.environ, {'PATH':str(self.bin)+os.pathsep+os.environ['PATH']}):
            self.env_cli('peer','--task','T1','--actor','codex:a','--to','claude-code','--kind','verify','--id','verify')
        state=self.state()
        self.assertFalse(gm.blockers(state,'T1'))
        self.assertEqual(state['tasks']['T1']['status'],'building')
        self.assertIsNone(state['tasks']['T1']['review'])
        self.apply(dict(id='resubmit',op='submit',actor='codex:a',task='T1',head=self.head,summary='corrected',evidence='verified',not_done='none',next='review'))
        final=self.peer('final-review'); self.assertEqual(final.returncode,0,final.stderr)

    def test_remediation_cannot_bypass_collision(self):
        self.apply(dict(id='collision',op='notice',actor='claude-code:b',task='T1',to='codex',kind='COLLISION',severity='S1',summary='writer collision',evidence='concurrent writer'))
        r=dict(id='plan',op='remediate',actor='codex:a',task='T1',notices=['collision'],scope=['app.py'],evidence='attempt')
        self.assertNotEqual(self.apply(r,ok=False).returncode,0)
        self.assertNotIn('remediation',self.state()['tasks']['T1'])

    def test_recovered_owner_can_cancel_predecessor_orphan(self):
        ledger=gm.Ledger(self.root);ctx=gm.context_at(self.root);ctx['runtime_record']=True
        ledger.apply(dict(id='lost-start',op='capture',actor='codex:a',task='T1',report=dict(kind='peer-start',max_runs=3)),ctx)
        self.apply(dict(id='recover-task',op='recover',actor='codex:new',task='T1',expected_owner='codex:a',to='codex:new',authorization='Continue abandoned task',evidence='Old writer stopped'),authorize=True)
        recovery=dict(id='recover-run',op='recover-run',actor='codex:new',run='lost',authorization='Continue abandoned task',evidence='Process stopped')
        self.assertNotEqual(self.apply(recovery,ok=False).returncode,0)
        self.apply(recovery,authorize=True)
        self.assertEqual(self.state()['runs']['lost']['original_actor'],'codex:a')
        self.assertEqual(self.state()['runs']['lost']['actor'],'codex:new')

    def test_completion_publication_is_atomic_and_retry_does_not_execute(self):
        from types import SimpleNamespace
        self.submit()
        args=SimpleNamespace(task='T1',actor='codex:a',to='claude-code',kind='review',id='atomic',model=None,timeout=5,max_turns=8,max_dollars=2,adapter='exec',resume_run=None,max_runs=3)
        original=gm.Ledger.apply
        def fail(ledger,request,ctx):
            if request['op']=='peer-complete':
                # Validate the whole transition, then simulate failure before ref publication.
                gm.transition(ledger.load()[1],request,ctx)
                raise gm.Error('simulated publication outage')
            return original(ledger,request,ctx)
        with patch.dict(os.environ,{'PATH':str(self.bin)+os.pathsep+os.environ['PATH']}),patch.object(gm.Ledger,'apply',fail):
            with self.assertRaisesRegex(gm.Error,'simulated'):
                rt.peer(self.root,args,rt.api(gm.__dict__))
        state=self.state(); self.assertEqual(state['tasks']['T1']['status'],'review')
        self.assertIsNone(state['tasks']['T1']['review']);self.assertNotIn('atomic',state['runs'])
        with patch.object(rt,'cli_capability',side_effect=AssertionError('must not call CLI')):
            result=rt.peer(self.root,args,rt.api(gm.__dict__))
        self.assertTrue(result['passed']);self.assertEqual(self.state()['tasks']['T1']['status'],'approved')
        self.assertIn('atomic',self.state()['runs'])

    def test_failed_verification_keeps_defects_blocking(self):
        self.submit(); self.peer('bad', 'changes')
        self.apply(dict(id='fix-plan',op='remediate',actor='codex:a',task='T1',notices=['bad-finding-0'],scope=['app.py'],evidence='Correct defect'))
        with patch.dict(os.environ,{'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],'GM_FIXTURE_MODE':'changes'}):
            self.env_cli('peer','--task','T1','--actor','codex:a','--to','claude-code','--kind','verify','--id','still-bad')
        state=self.state()
        self.assertNotEqual(state['notices']['bad-finding-0']['status'],'resolved')
        self.assertTrue(gm.blockers(state,'T1'))
        self.assertIsNone(state['tasks']['T1']['review'])
        self.assertNotEqual(cli(self.root,'guard','--task','T1','--actor','codex:a','app.py',ok=False).returncode,0)

    def test_check_detects_two_equally_stale_copies(self):
        for name in ('.agents/skills/gridmatrix', '.claude/skills/gridmatrix'):
            path=self.root/name/'scripts/gm_runtime.py'
            path.write_text(path.read_text()+'\n# stale copied runtime\n')
        result=cli(self.root,'check',ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('differ from running skill',result.stderr)
        doctor=json.loads(cli(self.root,'doctor').stdout)
        self.assertFalse(doctor['installation']['copies']['.agents/skills/gridmatrix']['matches_running_skill'])

    def test_run_output_limit_and_timeout(self):
        output=rt.run_process([sys.executable,'-c','print("x"*100000)'],self.root,self.base/'out',2,cap=1024)
        self.assertEqual(output['status'],'output-limit')
        timed=rt.run_process([sys.executable,'-c','import time; time.sleep(10)'],self.root,self.base/'timed',1)
        self.assertEqual(timed['status'],'timeout')

if __name__=='__main__': unittest.main()
