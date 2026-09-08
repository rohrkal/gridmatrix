import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_gridmatrix import SCRIPT, cli, run, repo, claim, gm

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
result={'verdict':'pass','findings':[],'summary':'Fixture inspected source','limits':'Synthetic fixture; no live model'}
if mode=='changes':
 result.update(verdict='changes',findings=[dict(severity='S1',location='app.py:1',problem='Fixture defect',evidence='Controlled reproduction')])
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
            p = self.bin / name; p.write_text(FAKE); p.chmod(0o755)

    def apply(self, value, ok=True, authorize=False):
        return cli(self.root, 'apply', *(['--authorize-recovery'] if authorize else []), '-', data=json.dumps(value), ok=ok)

    def submit(self):
        self.apply(dict(id='submit', op='submit', actor='codex:a', task='T1', head=self.head,
                        summary='submitted', evidence='baseline', not_done='none', next='review'))

    def peer(self, rid='peer1', mode='pass', to='claude-code', adapter='exec', timeout=5):
        env = {'PATH': str(self.bin) + os.pathsep + os.environ['PATH'], 'GM_FIXTURE_MODE': mode}
        with patch.dict(os.environ, env):
            return cli(self.root, 'peer', '--task', 'T1', '--actor', 'codex:a', '--to', to,
                       '--adapter', adapter, '--id', rid, '--timeout', str(timeout), ok=False)

    def state(self):
        return gm.Ledger(self.root).load()[1]

    def test_doctor_does_not_infer_authentication(self):
        with patch.dict(os.environ, {'PATH': str(self.bin) + os.pathsep + os.environ['PATH']}):
            d = json.loads(cli(self.root, 'doctor').stdout)
        self.assertTrue(d['platforms']['codex']['installed'])
        self.assertEqual(d['platforms']['codex']['authentication'], 'unverified')
        self.assertFalse(d['live_pair_ready'])

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
            result=cli(self.root,*args,ok=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(self.state()['tasks']['T2']['status'],'review')
        args[args.index('rpc1')]='rpc2'; args+=['--resume-run','rpc1']
        with patch.dict(os.environ, {'PATH':str(self.bin)+os.pathsep+os.environ['PATH'],'GM_FIXTURE_MODE':'pass'}):
            result=cli(self.root,*args,ok=False)
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
            result = cli(self.root, 'peer', '--task', 'T2', '--actor', 'claude-code:b', '--to', 'codex', '--id', 'exec1')
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
        binary = self.bin / 'noisy'
        binary.write_text('#!/usr/bin/env python3\nimport sys,time\nsys.stderr.write("x"*5000000);sys.stderr.flush();time.sleep(10)\n')
        binary.chmod(0o755)
        folder = self.base / 'rpc-noise'; folder.mkdir()
        result = gm_appserver.execute(str(binary), self.root, folder, 'review', rt.REVIEW_SCHEMA, 2, dict(os.environ))
        self.assertEqual(result['status'], 'output-limit')
        self.assertLessEqual((folder / 'stderr.log').stat().st_size, 4 * 1024 * 1024)

    def test_run_output_limit_and_timeout(self):
        output=rt.run_process([sys.executable,'-c','print("x"*100000)'],self.root,self.base/'out',2,cap=1024)
        self.assertEqual(output['status'],'output-limit')
        timed=rt.run_process([sys.executable,'-c','import time; time.sleep(10)'],self.root,self.base/'timed',1)
        self.assertEqual(timed['status'],'timeout')

if __name__=='__main__': unittest.main()
