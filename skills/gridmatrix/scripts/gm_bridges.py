"""Opt-in Claude hooks and a minimal stdio MCP adapter for the same ledger CLI."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


def invoke(root, args, payload, g):
    script = Path(__file__).with_name('gridmatrix.py')
    p = subprocess.run([sys.executable, str(script), '--repo', str(root), *args],
                       input=json.dumps(payload) if payload is not None else None,
                       capture_output=True, text=True, timeout=180)
    g.require(p.returncode == 0, p.stderr.strip() or 'Gridmatrix request failed')
    return json.loads(p.stdout)


def hooks(root, install, g):
    if install:
        g.require(os.name == 'posix', 'automatic hook installation supports POSIX shells; configure the documented command manually on Windows')
        path = root / '.claude/settings.json'; g.safe_target(root, path)
        settings = json.loads(path.read_text()) if path.exists() else {}
        script = root / '.agents/skills/gridmatrix/scripts/gridmatrix.py'
        # Relative to the discovered project root: portable to another checkout.
        command = 'python3' + ' "$CLAUDE_PROJECT_DIR/.agents/skills/gridmatrix/scripts/gridmatrix.py" --repo "$CLAUDE_PROJECT_DIR" hook'
        table = settings.setdefault('hooks', {})
        for event, matcher in [('SessionStart', ''), ('PreToolUse', 'Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell')]:
            entries = table.setdefault(event, [])
            if not any(any(h.get('command') == command for h in e.get('hooks', [])) for e in entries):
                entries.append({'matcher': matcher, 'hooks': [{'type': 'command', 'command': command}]})
        g.write_atomic(path, g.dumps(settings))
        return {'installed': True, 'path': str(path), 'requires': 'GRIDMATRIX_ACTOR and GRIDMATRIX_TASK for writes; existing hooks preserved'}
    import gm_runtime as rt
    event = json.load(sys.stdin)
    if event.get('hook_event_name') == 'SessionStart':
        result = invoke(root, ['status'], None, g)
        return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': g.dumps(result)}}
    if event.get('hook_event_name') != 'PreToolUse':
        return {}
    name = event.get('tool_name'); data = event.get('tool_input', {})
    try:
        # Shell syntax cannot be exhaustively classified. Strict opt-in mode denies
        # shell tools; authorized checks run through the coordinator evidence runner.
        g.require(name not in ('Bash', 'PowerShell'), 'strict Gridmatrix hook blocks shell tools; run approved checks through the coordinator')
        paths = [data[k] for k in ('file_path', 'notebook_path') if isinstance(data.get(k), str)]
        g.require(paths, 'cannot determine write destination')
        rt.guard(root, os.environ.get('GRIDMATRIX_TASK'), os.environ.get('GRIDMATRIX_ACTOR'), paths, g)
        return {}  # Defer to existing platform permissions; ownership grants no new permission.
    except g.Error as exc:
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                      'permissionDecisionReason': str(exc)}}


def serve(root, who, g):
    g.actor(who)
    aliases = {'claim_task': 'claim', 'report_defect': 'notice', 'submit_review': 'review', 'transact': None}
    allowed = {'claim', 'submit', 'review', 'notice', 'ack', 'resolve', 'dispute', 'learn', 'confirm', 'retire', 'measure', 'lesson-outcome', 'remediate'}
    initialized = False
    for line in sys.stdin:
        request = None
        try:
            g.require(len(line) <= 1024 * 1024, 'request exceeds 1 MiB')
            request = json.loads(line)
            g.require(isinstance(request, dict) and request.get('jsonrpc') == '2.0', 'invalid JSON-RPC request')
            if 'id' not in request:
                continue
            method = request.get('method'); params = request.get('params') or {}
            if method == 'initialize':
                requested = params.get('protocolVersion')
                version = requested if requested in ('2024-11-05', '2025-03-26', '2025-06-18') else '2025-06-18'
                result = {'protocolVersion': version, 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'gridmatrix', 'version': g.VERSION}}
                initialized = True
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                g.require(initialized, 'initialize first')
                result = {'tools': [{'name': 'read_inbox', 'description': 'Read current tasks, notices and lessons without builder rationale.',
                                     'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
                                    *[{'name': name, 'description': 'Apply a Gridmatrix ' + (op or 'allowed protocol') + ' request. Actor is fixed by server configuration.',
                                       'inputSchema': {'type': 'object', 'properties': {'request': {'type': 'object'}}, 'required': ['request'], 'additionalProperties': False}}
                                      for name, op in aliases.items()]]}
            elif method == 'tools/call':
                g.require(initialized, 'initialize first')
                name = params.get('name'); arguments = params.get('arguments') or {}
                try:
                    if name == 'read_inbox':
                        value = invoke(root, ['status'], None, g)
                    else:
                        g.require(name in aliases, 'unknown tool')
                        body = dict(arguments['request']); body['actor'] = who
                        if aliases[name]: body['op'] = aliases[name]
                        g.require(body.get('op') in allowed, 'operation requires the operator CLI, not MCP')
                        value = invoke(root, ['apply', '-'], body, g)
                    result = {'content': [{'type': 'text', 'text': g.dumps(value)}], 'isError': False}
                except (g.Error, KeyError, TypeError, ValueError, subprocess.TimeoutExpired) as exc:
                    result = {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True}
            else:
                print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'error': {'code': -32601, 'message': 'method not found'}}), flush=True)
                continue
            reply = {'jsonrpc': '2.0', 'id': request['id'], 'result': result}
        except (g.Error, ValueError, TypeError) as exc:
            reply = {'jsonrpc': '2.0', 'id': request.get('id') if isinstance(request, dict) else None,
                     'error': {'code': -32600, 'message': str(exc)}}
        print(json.dumps(reply), flush=True)
