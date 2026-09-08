import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/gridmatrix/scripts/gridmatrix.py'
spec = importlib.util.spec_from_file_location('gm', SCRIPT)
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)


def run(root, *args, ok=True):
    p = subprocess.run(['git', '-C', str(root), *args], text=True, capture_output=True)
    if ok and p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


def repo(path):
    path.mkdir()
    run(path, 'init', '-b', 'main')
    run(path, 'config', 'user.name', 'Test')
    run(path, 'config', 'user.email', 'test@localhost')
    (path / 'app.py').write_text('answer = 42\n')
    run(path, 'add', 'app.py'); run(path, 'commit', '-m', 'baseline')
    return path


def write_fixture_cli(bindir, name, source):
    """Install a fake CLI that shutil.which() finds and subprocess runs directly.

    POSIX uses the shebang plus the executable bit. Windows honours neither, so an
    extensionless script is invisible to shutil.which(): it matches only PATHEXT
    entries. A .cmd shim is both discoverable and executable by CreateProcess
    without a shell, which keeps the fixtures identical on both platforms.
    """
    if os.name == 'nt':
        (bindir / (name + '.py')).write_text(source, encoding='utf-8')
        (bindir / (name + '.cmd')).write_text(
            '@echo off\r\n"{}" "%~dp0{}.py" %*\r\n'.format(sys.executable, name), encoding='utf-8')
        return bindir / (name + '.cmd')
    path = bindir / name
    path.write_text(source, encoding='utf-8')
    path.chmod(0o755)
    return path


def cli(root, *args, ok=True, data=None):
    p = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(root), *args],
                       input=data, text=True, capture_output=True)
    if ok and p.returncode:
        raise AssertionError(p.stderr)
    return p


def claim(tid='T1', who='codex:a', scope=None):
    return {'id': 'claim-' + tid, 'op': 'claim', 'actor': who, 'task': tid,
            'goal': 'Improve answer', 'base': 'a' * 40,
            'scope': scope or ['app.py'], 'acceptance': ['Answer remains 42']}

class StateTests(unittest.TestCase):
    def setUp(self):
        self.ctx = {'workspace': 'host:/one', 'branch': 'gm/task', 'head': 'b' * 40}
        self.state = gm.transition(gm.empty(), claim(), self.ctx)

    def request(self, op, who='codex:a', **extra):
        return dict(id=op + '-1', op=op, actor=who, task='T1', **extra)

    def submit(self):
        return gm.transition(self.state, self.request('submit', head=self.ctx['head'],
                             summary='done', evidence='test exit 0', not_done='none', next='review'), self.ctx)

    def test_duplicate_and_reused_request_id(self):
        self.assertEqual(self.state, gm.transition(self.state, claim(), self.ctx))
        r = claim(); r['goal'] = 'different'
        with self.assertRaises(gm.Error): gm.transition(self.state, r, self.ctx)

    def test_scope_parent_child_and_case_overlap(self):
        for path in ['app.py', 'app.py/sub', 'APP.py', '.']:
            with self.assertRaises(gm.Error):
                gm.transition(self.state, claim('T2', scope=[path]), dict(self.ctx, workspace='host:/two', branch='other'))

    def test_disjoint_scope_still_rejects_same_workspace_or_branch(self):
        for ctx in [self.ctx, dict(self.ctx, workspace='elsewhere')]:
            with self.assertRaises(gm.Error): gm.transition(self.state, claim('T2', scope=['docs']), ctx)
        result = gm.transition(self.state, claim('T2', scope=['docs']), dict(self.ctx, workspace='elsewhere', branch='gm/other'))
        self.assertEqual(len(result['tasks']), 2)

    def test_invalid_scope_and_actor(self):
        for path in ['../secret', '/tmp/foo', '.git/config', 'src/*', 'a\\b']:
            with self.assertRaises(gm.Error): gm.transition(gm.empty(), claim(scope=[path]), self.ctx)
        with self.assertRaises(gm.Error): gm.transition(gm.empty(), claim(who='fake:a'), self.ctx)

    def test_review_requires_other_platform_and_exact_head(self):
        s = self.submit()
        with self.assertRaises(gm.Error):
            gm.transition(s, self.request('review', 'claude-code:b', head=self.ctx['head'],
                          verdict='pass', evidence='verified', limits='none'), self.ctx)
        for who, head in [('codex:another-session', self.ctx['head']), ('claude-code:b', 'c' * 40)]:
            with self.assertRaises(gm.Error):
                gm.transition(s, self.request('review', who, head=head, verdict='pass', evidence='verified', limits='none'), dict(self.ctx, workspace='host:/review'))
        s = gm.transition(s, self.request('review', 'claude-code:b', head=self.ctx['head'], verdict='pass', evidence='verified', limits='none'), dict(self.ctx, workspace='host:/review'))
        self.assertEqual(s['tasks']['T1']['status'], 'approved')
        r = self.request('submit', head=self.ctx['head'], summary='again', evidence='tests', not_done='none', next='review')
        r['id'] = 'new-submit'
        s = gm.transition(s, r, self.ctx)
        self.assertIsNone(s['tasks']['T1']['review'])

    def test_ack_and_dispute_do_not_clear_blocker(self):
        n = self.request('notice', 'claude-code:b', to='codex', kind='DEFECT', severity='S1', summary='bad', evidence='repro')
        s = gm.transition(self.state, n, self.ctx)
        for op in ['ack', 'dispute']:
            s = gm.transition(s, self.request(op, notice=n['id'], evidence='answer'), self.ctx)
            self.assertTrue(gm.blockers(s, 'T1'))
        with self.assertRaises(gm.Error):
            gm.transition(s, self.request('resolve', notice=n['id'], evidence='fixed'), self.ctx)
        s = gm.transition(s, self.request('resolve', 'claude-code:b', notice=n['id'], evidence='verified fix'), self.ctx)
        self.assertFalse(gm.blockers(s, 'T1'))

    def test_collision_always_blocks_and_global_blocks_claim(self):
        n = self.request('notice', 'claude-code:b', to='codex', kind='COLLISION', severity='S3', summary='overlap', evidence='diff')
        n['task'] = '*'
        s = gm.transition(self.state, n, self.ctx)
        self.assertTrue(gm.blockers(s, 'any-task'))
        with self.assertRaises(gm.Error):
            gm.transition(s, claim('T2', scope=['docs']), dict(self.ctx, workspace='other', branch='other'))

    def test_lessons_require_peer_confirmation_and_keep_history(self):
        r = dict(id='lesson1', op='learn', actor='codex:a', scope='app.py', rule='Check boundary', evidence='notice 17')
        s = gm.transition(self.state, r, self.ctx)
        with self.assertRaises(gm.Error):
            gm.transition(s, dict(id='confirm1', op='confirm', actor='codex:other', lesson='lesson1', evidence='yes'), self.ctx)
        for op in ['confirm', 'retire']:
            s = gm.transition(s, dict(id=op, op=op, actor='claude-code:b', lesson='lesson1', evidence='verified'), self.ctx)
        self.assertEqual(s['lessons']['lesson1']['status'], 'retired')
        self.assertIn('lesson1', s['receipts'])

    def test_finish_needs_approval_and_wrong_owner_cannot_cancel(self):
        with self.assertRaises(gm.Error):
            gm.transition(self.state, self.request('finish', head=self.ctx['head'], evidence='merged'), self.ctx)
        with self.assertRaises(gm.Error):
            gm.transition(self.state, self.request('cancel', 'claude-code:b', evidence='gone'), self.ctx)

class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = repo(self.base / 'project with spaces')

    def install(self, remote=None):
        cli(self.root, 'init', *(['--remote', remote] if remote else []))
        run(self.root, 'add', 'AGENTS.md', 'CLAUDE.md', '.agents', '.claude', '.gridmatrix')
        run(self.root, 'commit', '-m', 'adopt')
        run(self.root, 'checkout', '-b', 'gm/task')

    def test_init_preserves_both_histories_and_is_idempotent(self):
        (self.root / 'AGENTS.md').write_text('Existing Codex rules\n')
        (self.root / 'CLAUDE.md').write_text('Existing Claude rules\n')
        original = run(self.root, 'status', '--porcelain')
        cli(self.root, 'init', '--dry-run')
        self.assertEqual(original, run(self.root, 'status', '--porcelain'))
        cli(self.root, 'init')
        before = {str(f.relative_to(self.root)): f.read_bytes() for f in self.root.rglob('*') if f.is_file() and '.git' not in f.parts}
        cli(self.root, 'init')
        after = {str(f.relative_to(self.root)): f.read_bytes() for f in self.root.rglob('*') if f.is_file() and '.git' not in f.parts}
        self.assertEqual(before, after)
        self.assertIn('Existing Codex rules', (self.root / 'AGENTS.md').read_text())
        self.assertIn('Existing Claude rules', (self.root / 'CLAUDE.md').read_text())
        cli(self.root, 'check')

    def test_malformed_markers_preflight_does_not_write(self):
        (self.root / 'AGENTS.md').write_text(gm.BEGIN + '\nkeep this\n')
        self.assertNotEqual(cli(self.root, 'init', ok=False).returncode, 0)
        self.assertFalse((self.root / '.gridmatrix').exists())
        self.assertEqual((self.root / 'AGENTS.md').read_text(), gm.BEGIN + '\nkeep this\n')

    def test_symlink_target_refused(self):
        outside = self.base / 'outside'; outside.mkdir()
        try:
            (self.root / '.claude').symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            # Windows needs SeCreateSymbolicLinkPrivilege (Developer Mode or admin).
            # The refusal path itself is platform-independent; only creating the
            # symlink to test it is gated, so skip explicitly rather than fail.
            raise unittest.SkipTest('cannot create symlink in this environment: ' + str(exc))
        self.assertNotEqual(cli(self.root, 'init', ok=False).returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.root / '.gridmatrix').exists())

    def test_greenfield_install_without_commit(self):
        fresh = self.base / 'fresh'; fresh.mkdir(); run(fresh, 'init')
        cli(fresh, 'init'); cli(fresh, 'check')

    def test_worktree_shared_atomic_claim_race(self):
        self.install()
        other = self.base / 'other'
        run(self.root, 'worktree', 'add', '-b', 'gm/other', str(other), 'HEAD')
        base = run(self.root, 'rev-parse', 'HEAD')
        def attempt(pair):
            path, tid = pair
            r = claim(tid); r['base'] = base
            return cli(path, 'apply', '-', data=json.dumps(r), ok=False)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(attempt, [(self.root, 'T1'), (other, 'T2')]))
        self.assertEqual(sorted(x.returncode for x in results), [0, 1])
        for path in [self.root, other]:
            state = json.loads(cli(path, 'status').stdout)['state']
            self.assertEqual(len(state['tasks']), 1)
            self.assertEqual(run(path, 'status', '--porcelain'), '')

    def test_remote_clone_claim_race_and_failed_network(self):
        bare = self.base / 'remote.git'; bare.mkdir(); run(bare, 'init', '--bare')
        run(self.root, 'remote', 'add', 'origin', str(bare))
        self.install('origin')
        run(self.root, 'push', 'origin', 'HEAD:main')
        other = self.base / 'cloud clone'
        run(self.base, 'clone', '-b', 'main', str(bare), str(other))
        run(other, 'checkout', '-b', 'gm/other')
        base = run(self.root, 'rev-parse', 'HEAD')
        def attempt(pair):
            path, tid = pair
            r = claim(tid); r['base'] = base
            return cli(path, 'apply', '-', data=json.dumps(r), ok=False)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(attempt, [(self.root, 'T1'), (other, 'T2')]))
        self.assertEqual(sorted(x.returncode for x in results), [0, 1], [x.stderr for x in results])
        a = json.loads(cli(self.root, 'status').stdout)
        b = json.loads(cli(other, 'status').stdout)
        self.assertEqual(a['ledger_commit'], b['ledger_commit'])
        self.assertEqual(len(a['state']['tasks']), 1)
        run(other, 'remote', 'set-url', 'origin', str(self.base / 'unavailable'))
        self.assertNotEqual(cli(other, 'status', ok=False).returncode, 0)
        self.assertEqual(run(other, 'for-each-ref', 'refs/gridmatrix/state'), '')

    def test_submit_scope_check_and_full_lifecycle(self):
        self.install()
        base = run(self.root, 'rev-parse', 'HEAD')
        r = claim(); r['base'] = base
        cli(self.root, 'apply', '-', data=json.dumps(r))
        (self.root / 'outside.py').write_text('unexpected\n')
        run(self.root, 'add', 'outside.py'); run(self.root, 'commit', '-m', 'outside')
        head = run(self.root, 'rev-parse', 'HEAD')
        submit = dict(id='submit', op='submit', actor='codex:a', task='T1', head=head,
                      summary='done', evidence='test passed', not_done='none', next='review')
        self.assertIn('out-of-scope', cli(self.root, 'apply', '-', data=json.dumps(submit), ok=False).stderr)
        run(self.root, 'revert', '--no-edit', 'HEAD')
        (self.root / 'app.py').write_text('answer = 6 * 7\n')
        run(self.root, 'add', 'app.py'); run(self.root, 'commit', '-m', 'answer')
        head = run(self.root, 'rev-parse', 'HEAD'); submit['head'] = head
        cli(self.root, 'apply', '-', data=json.dumps(submit))
        public = json.loads(cli(self.root, 'status').stdout)['state']['tasks']['T1']
        self.assertNotIn('handoff', public)
        explicit = json.loads(cli(self.root, 'status', '--handoff', 'T1').stdout)['state']
        self.assertEqual(explicit['handoff']['summary'], 'done')
        review = dict(id='review', op='review', actor='claude-code:b', task='T1', head=head,
                      verdict='pass', evidence='checked', limits='none')
        other = self.base / 'review'
        run(self.root, 'worktree', 'add', '--detach', str(other), head)
        cli(other, 'apply', '-', data=json.dumps(review))
        commands = self.base / 'checks.json'
        commands.write_text(json.dumps([[sys.executable, '-c', 'import app; assert app.answer == 42']]))
        cli(self.root, 'integrate', '--task', 'T1', '--actor', 'codex:a', '--id', 'integration', '--target', 'refs/heads/main', '--commands', str(commands))
        cli(self.root, 'check', '--task', 'T1')
        (self.root / 'app.py').write_text('answer = 43\n')
        self.assertNotEqual(cli(self.root, 'check', '--task', 'T1', ok=False).returncode, 0)
        (self.root / 'app.py').write_text('answer = 6 * 7\n')
        run(self.root, 'update-ref', 'refs/heads/main', head)
        cli(self.root, 'apply', '-', data=json.dumps(dict(id='finish', op='finish', actor='codex:a', task='T1', head=head, integrated_commit=head, evidence='accepted at head')))
        self.assertEqual(json.loads(cli(self.root, 'status').stdout)['state']['tasks'], {})

class PortabilityTests(unittest.TestCase):
    """Regressions for defects that only appear off a POSIX/UTF-8 locale machine.

    Requested by Codex in notice-review-plan-3608: cover Unicode inherited
    instructions and the literal ledger blob name, not just ASCII fixtures.
    """

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: None)
        self.root = repo(self.base / 'project')

    def test_ledger_blob_is_named_ledger_json_exactly(self):
        # git mktree takes the entry name up to the newline. Passing its stdin in
        # text mode on Windows appended CR, storing the blob as "ledger.json\r" so
        # every later read failed with "not a Gridmatrix ledger".
        cli(self.root, 'init')
        run(self.root, 'add', '-A'); run(self.root, 'commit', '-m', 'gridmatrix setup')
        head = run(self.root, 'rev-parse', 'HEAD')
        c = claim(); c['base'] = head
        cli(self.root, 'apply', '-', data=json.dumps(c))
        ref = run(self.root, 'rev-parse', 'refs/gridmatrix/state')
        names = run(self.root, 'ls-tree', '--name-only', ref).splitlines()
        self.assertEqual(names, ['ledger.json'])
        for name in names:
            self.assertNotIn('\r', name)
        # The ledger must also be readable back through the normal path.
        self.assertIn('T1', json.loads(cli(self.root, 'status').stdout)['state']['tasks'])

    def test_unicode_inherited_instructions_survive_install(self):
        # Reads once used the locale encoding while writes used UTF-8, so on a
        # cp1252 console non-ASCII text was silently re-encoded into mojibake.
        text = '# Réglages\n\nUtilise « — » et →, díaz, 日本語.\n'
        (self.root / 'AGENTS.md').write_text(text, encoding='utf-8')
        cli(self.root, 'init')
        after = (self.root / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('Utilise « — » et →, díaz, 日本語.', after)
        self.assertIn(gm.BEGIN, after)
        cli(self.root, 'check')

    def test_installed_copies_match_source_byte_for_byte(self):
        # check() and installation_freshness() compare with read_bytes(), so the
        # installer must reproduce bytes rather than decoded-and-re-encoded text.
        cli(self.root, 'init')
        source = SCRIPT.resolve().parents[1]
        checked = 0
        for src in source.rglob('*'):
            if src.is_file() and '__pycache__' not in src.parts and src.suffix != '.pyc':
                for dest in ('.agents/skills/gridmatrix', '.claude/skills/gridmatrix'):
                    target = self.root / dest / src.relative_to(source)
                    self.assertTrue(target.is_file(), 'missing copy: ' + str(target))
                    self.assertEqual(target.read_bytes(), src.read_bytes(),
                                     'installed copy differs from source: ' + str(src))
                    checked += 1
        self.assertGreater(checked, 0)

    def test_install_copies_non_utf8_asset_without_corruption(self):
        # rglob copies every file, so one binary asset must not break init.
        source = SCRIPT.resolve().parents[1]
        asset = source / 'assets' / 'portability_probe.bin'
        blob = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + bytes(range(256))
        asset.write_bytes(blob)
        self.addCleanup(asset.unlink)
        cli(self.root, 'init')
        for dest in ('.agents/skills/gridmatrix', '.claude/skills/gridmatrix'):
            self.assertEqual((self.root / dest / 'assets' / 'portability_probe.bin').read_bytes(), blob)

if __name__ == '__main__':
    unittest.main()
