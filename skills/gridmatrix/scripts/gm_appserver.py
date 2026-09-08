"""Codex App Server v2 JSON-RPC adapter, bounded to one read-only review turn."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time


def execute(binary, cwd, folder, prompt, schema, timeout, env, model=None, resume=None):
    started = time.monotonic()
    events = queue.Queue(maxsize=16)
    logs = []
    child = None
    thread_id = resume
    final = None
    status, error = 'failed', None
    total = 0
    stopped = threading.Event()
    reader_thread = None

    def enqueue(value):
        while not stopped.is_set():
            try:
                events.put(value, timeout=0.1); return
            except queue.Full:
                continue

    def reader(stream):
        try:
            read_bytes = 0
            while read_bytes <= 4 * 1024 * 1024 and not stopped.is_set():
                line = stream.readline(4 * 1024 * 1024 + 1 - read_bytes)
                if not line:
                    break
                read_bytes += len(line.encode())
                enqueue(line)
        finally:
            enqueue(None)

    try:
        with (folder / 'stderr.log').open('w', encoding='utf-8') as err:
            child = subprocess.Popen([binary, 'app-server'], cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=err, text=True, encoding='utf-8', errors='replace',
                                     **({'start_new_session': True} if os.name == 'posix' else {}))
            reader_thread = threading.Thread(target=reader, args=(child.stdout,), daemon=True)
            reader_thread.start()

            def send(value):
                child.stdin.write(json.dumps(value) + '\n'); child.stdin.flush()

            send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                  'params': {'clientInfo': {'name': 'gridmatrix', 'version': '2.1.1'}, 'capabilities': {}}})
            turn_id = None
            while time.monotonic() - started < timeout:
                if total + (folder / 'stderr.log').stat().st_size > 4 * 1024 * 1024:
                    status = 'output-limit'; break
                try:
                    line = events.get(timeout=min(0.2, max(0.01, timeout - (time.monotonic() - started))))
                except queue.Empty:
                    if child.poll() is not None:
                        break
                    continue
                if line is None:
                    break
                total += len(line.encode())
                if total + (folder / 'stderr.log').stat().st_size > 4 * 1024 * 1024:
                    status = 'output-limit'; break
                logs.append(line)
                msg = json.loads(line)
                if msg.get('error'):
                    error = 'App Server returned an RPC error'; break
                if msg.get('id') == 1 and 'result' in msg:
                    send({'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
                    params = {'cwd': str(cwd), 'approvalPolicy': 'never', 'sandbox': 'read-only'}
                    if model: params['model'] = model
                    if resume: params['threadId'] = resume
                    send({'jsonrpc': '2.0', 'id': 2, 'method': 'thread/resume' if resume else 'thread/start', 'params': params})
                elif msg.get('id') == 2 and 'result' in msg:
                    thread_id = msg['result']['thread']['id']
                    send({'jsonrpc': '2.0', 'id': 3, 'method': 'turn/start', 'params': {
                        'threadId': thread_id, 'input': [{'type': 'text', 'text': prompt}],
                        'outputSchema': schema, 'approvalPolicy': 'never', 'sandboxPolicy': {'type': 'readOnly'}}})
                elif msg.get('id') == 3 and 'result' in msg:
                    turn_id = msg['result']['turn']['id']
                elif msg.get('method') == 'item/completed':
                    item = msg.get('params', {}).get('item', {})
                    if item.get('type') == 'agentMessage':
                        final = item.get('text')
                elif msg.get('method') == 'turn/completed':
                    turn = msg.get('params', {}).get('turn', {})
                    if turn.get('status') == 'completed' and final is not None:
                        (folder / 'result.json').write_text(final, encoding='utf-8')
                        status = 'passed'
                    else:
                        error = 'turn failed, was interrupted, or produced no structured result'
                    break
                elif 'id' in msg and 'method' in msg:
                    # No broad approvals are granted by the coordinator. Surface the block.
                    send({'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32000, 'message': 'Gridmatrix review cannot grant additional permissions'}})
                    if thread_id and turn_id:
                        send({'jsonrpc': '2.0', 'id': 99, 'method': 'turn/interrupt', 'params': {'threadId': thread_id, 'turnId': turn_id}})
                    error = 'peer requested additional input or permissions'; break
            else:
                status = 'timeout'
    except (OSError, ValueError, KeyError, TypeError) as exc:
        error = str(exc)
    finally:
        stopped.set()
        if child is not None:
            if os.name == 'posix':
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            elif child.poll() is None:
                subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'], capture_output=True, timeout=10)
                child.kill()
            child.wait(timeout=10)
            if reader_thread is not None: reader_thread.join(timeout=1)
            child.stdin.close()
            child.stdout.close()
        from gm_runtime import scrub
        (folder / 'stdout.log').write_text(scrub(''.join(logs)), encoding='utf-8')
        err = folder / 'stderr.log'
        if err.exists():
            with err.open(encoding='utf-8', errors='replace') as stream:
                tail = stream.read(4 * 1024 * 1024)
            err.write_text(scrub(tail), encoding='utf-8')
    return {'status': status, 'exit_code': child.returncode if child is not None else None,
            'seconds': round(time.monotonic() - started, 3), 'session_id': thread_id,
            'adapter': 'app-server', 'error': scrub(error) if error else None}
