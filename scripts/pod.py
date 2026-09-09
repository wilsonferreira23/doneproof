#!/usr/bin/env python3
"""DoneProof: explicit contracts, versioned evidence, one completion decision."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = '3.0.0'
SCHEMA = 3
LIMITS = {'light': 4, 'standard': 7, 'strict': 12}
MAX_OUTPUT = 1024 * 1024
MAX_INPUT = 256 * 1024 * 1024
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z')
SENSITIVE = re.compile(r'token|secret|password|api.?key|authorization|cookie', re.I)


class Blocked(Exception):
    pass


def need(condition, message):
    if not condition:
        raise Blocked(message)


def object_fields(value, allowed, required, where):
    need(isinstance(value, dict), f'{where}: expected object')
    need(not (set(value) - set(allowed)), f'{where}: unknown fields {sorted(set(value) - set(allowed))}')
    need(set(required) <= set(value), f'{where}: missing fields {sorted(set(required) - set(value))}')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def names(value, where, nonempty=False):
    need(isinstance(value, list) and all(text(x) for x in value), f'{where}: expected string list')
    need(len(value) == len(set(value)), f'{where}: duplicates')
    need(not nonempty or bool(value), f'{where}: empty list')


def ident(value, where):
    need(isinstance(value, str) and ID.fullmatch(value), f'{where}: invalid id')


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, f'duplicate JSON key: {key}')
        result[key] = value
    return result


def load(path):
    need(path.stat().st_size <= 16 * MAX_OUTPUT, f'JSON too large: {path.name}')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.pod-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, indent=2, ensure_ascii=False, allow_nan=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def exclusive(folder):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / '.pod.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Blocked('another operation is running for this task') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def validate(contract):
    object_fields(contract, 'schema_version task_id root kind mode gates final_gate requirements plan_path plan_additions mutations supersedes'.split(),
                  'schema_version task_id root kind mode gates final_gate'.split(), 'contract')
    need(type(contract['schema_version']) is int and contract['schema_version'] == SCHEMA,
         'schema_version must be 3; create a new task for 2.2 migration')
    ident(contract['task_id'], 'task_id')
    need(text(contract['root']), 'root must be a path relative to the contract')
    need(contract['kind'] in ('task', 'plan'), 'kind must be task or plan')
    need(contract['mode'] in LIMITS, 'invalid mode')
    if 'supersedes' in contract:
        object_fields(contract['supersedes'], ['task_id', 'contract_sha256', 'reason'], ['task_id', 'contract_sha256', 'reason'], 'supersedes')
        need(all(text(v) for v in contract['supersedes'].values()), 'supersedes values must be text')
    gates = contract['gates']
    need(isinstance(gates, list) and bool(gates), 'gates must be a nonempty list')
    by_id = {}
    for gate in gates:
        object_fields(gate, 'id level inputs criteria excludes depends_on checks'.split(), 'id level inputs criteria checks'.split(), 'gate')
        gid = gate['id']
        ident(gid, 'gate')
        need(gid not in by_id, f'duplicate gate {gid}')
        by_id[gid] = gate
        need(gate['level'] in ('task', 'feature', 'milestone'), f'{gid}: invalid level')
        for key in ('inputs', 'criteria', 'excludes', 'depends_on'):
            names(gate.get(key, []), f'{gid}.{key}')
        checks = gate['checks']
        need(isinstance(checks, list) and 0 < len(checks) <= LIMITS[contract['mode']], f'{gid}: check count exceeds mode or is empty')
        seen = set()
        for check in checks:
            validate_check(check, gate)
            need(check['id'] not in seen, f'{gid}: duplicate check')
            seen.add(check['id'])
        need(gate['inputs'] or all(c['type'] == 'http' for c in checks), f'{gid}: declare product inputs')
    for gate in gates:
        need(set(gate.get('depends_on', [])) <= set(by_id), f"{gate['id']}: unknown dependency")
    ident(contract['final_gate'], 'final_gate')
    need(contract['final_gate'] in by_id, 'unknown final_gate')
    visiting, visited = set(), set()

    def walk(gid):
        need(gid not in visiting, f'cyclic gate dependency: {gid}')
        if gid in visited:
            return
        visiting.add(gid)
        for dep in by_id[gid].get('depends_on', []):
            walk(dep)
        visiting.remove(gid)
        visited.add(gid)

    for gid in by_id:
        walk(gid)
    requirements = contract.get('requirements', [])
    need(isinstance(requirements, list), 'requirements must be a list')
    seen = set()
    for req in requirements:
        object_fields(req, ['id', 'text', 'gate', 'source'], ['id', 'text', 'gate', 'source'], 'requirement')
        ident(req['id'], 'requirement')
        need(req['id'] not in seen, 'duplicate requirement')
        seen.add(req['id'])
        need(text(req['text']) and text(req['source']), 'requirement text/source must be nonempty')
        need(req['gate'] in by_id, 'unknown requirement gate')
    names(contract.get('plan_additions', []), 'plan_additions')
    if contract['kind'] == 'plan':
        need(text(contract.get('plan_path')) and requirements, 'plan requires plan_path and requirements')
        need(by_id[contract['final_gate']]['level'] != 'task', 'plan final must be feature or milestone')
    else:
        need(not requirements and 'plan_path' not in contract and not contract.get('plan_additions'), 'use kind=plan for requirements and saved plan')
    relevant = {contract['final_gate']} | {r['gate'] for r in requirements}
    closure = set()

    def include(gid):
        if gid not in closure:
            closure.add(gid)
            for dep in by_id[gid].get('depends_on', []):
                include(dep)

    for gid in relevant:
        include(gid)
    need(closure == set(by_id), 'every gate must serve a requirement or the final gate')
    roles = {c['purpose'] for g in gates for c in g['checks']}
    required = {'behavior'}
    if contract['mode'] != 'light' or contract['kind'] == 'plan':
        required.add('integration')
    if contract['mode'] == 'strict':
        required.add('negative')
    need(required <= roles, f'mode requires proof purposes: {sorted(required)}')
    if 'integration' in required:
        need(any(c['purpose'] == 'integration' for c in by_id[contract['final_gate']]['checks']), 'final gate requires integration proof')
    mutations = contract.get('mutations', [])
    need(isinstance(mutations, list), 'mutations must be a list')
    for mutation in mutations:
        object_fields(mutation, ['outcome', 'gate', 'check'], ['outcome', 'gate', 'check'], 'mutation')
        need(text(mutation['outcome']) and mutation['gate'] in by_id, 'mutation needs outcome and gate')
        checks = by_id[mutation['gate']]['checks']
        need(any(c['id'] == mutation['check'] and c['purpose'] == 'readback' for c in checks), 'mutation requires an explicit readback check')
    return by_id


def validate_check(check, gate):
    common = 'id type purpose timeout max_bytes'.split()
    fields = {'command': 'argv expect_exit stdout_contains cwd effect env_from',
              'file': 'path exists contains equals sha256',
              'http': 'url method headers headers_env expect_status expect_headers response_contains'}
    need(isinstance(check, dict) and check.get('type') in fields, 'unsupported check type')
    kind = check['type']
    object_fields(check, common + fields[kind].split(), ['id', 'type', 'purpose'], 'check')
    ident(check['id'], 'check')
    need(check['purpose'] in ('behavior', 'integration', 'negative', 'readback'), 'invalid proof purpose')
    for key in ('timeout', 'max_bytes'):
        value = check.get(key, 120 if key == 'timeout' else MAX_OUTPUT)
        need(type(value) in (int, float) and math.isfinite(value) and value > 0, f'{key}: expected positive number')
        if key == 'max_bytes':
            need(type(value) is int and value <= 16 * MAX_OUTPUT, 'max_bytes must be integer <= 16 MiB')
    for key in ('stdout_contains', 'contains', 'equals', 'response_contains', 'cwd'):
        if key in check:
            need(isinstance(check[key], str), f'{key}: expected text')
    for key in ('env_from', 'headers', 'headers_env', 'expect_headers'):
        if key in check:
            need(isinstance(check[key], dict) and all(text(k) and text(v) for k, v in check[key].items()), f'{key}: expected text mapping')
    if kind == 'command':
        need(isinstance(check.get('argv'), list) and check['argv'] and all(text(x) for x in check['argv']), 'command needs argv')
        need(type(check.get('expect_exit')) is int, 'command needs integer expect_exit')
        need(check.get('effect') in ('observe', 'isolated_test'), 'command effect must be observe or isolated_test')
        inline = len(check['argv']) > 2 and check['argv'][1] == '-c' and Path(check['argv'][0]).name.startswith('python')
        need(gate['criteria'] or inline, 'external test commands require protected criteria files')
    elif kind == 'file':
        need(text(check.get('path')), 'file needs path')
        need(type(check.get('exists', True)) is bool, 'exists must be boolean')
        need(check.get('exists', True) or not ({'contains', 'equals', 'sha256'} & set(check)), 'absent file cannot have content expectations')
        if 'sha256' in check:
            need(isinstance(check['sha256'], str) and re.fullmatch('[0-9a-f]{64}', check['sha256']), 'invalid sha256')
    else:
        need(text(check.get('url')), 'HTTP needs url')
        url = urllib.parse.urlsplit(check['url'])
        need(url.scheme in ('http', 'https') and url.hostname and not url.username, 'HTTP URL must have host and no credentials')
        need(check.get('method', 'GET') in ('GET', 'HEAD'), 'HTTP proof must observe with GET/HEAD; use isolated tests for writes')
        need(type(check.get('expect_status')) is int and 100 <= check['expect_status'] <= 599, 'explicit expect_status required')
        need(not any(SENSITIVE.search(k) for k in check.get('headers', {})), 'use headers_env for credentials')


def local_path(root, value):
    need(text(value) and not Path(value).is_absolute(), f'path must be relative to root: {value}')
    path = root / value
    need(path.resolve().is_relative_to(root), f'path leaves project root: {value}')
    for part in [path, *path.parents]:
        if part == root:
            break
        need(not part.is_symlink(), f'symlinks are not supported in proof inputs: {value}')
    return path


def file_stamp(path):
    if not path.exists():
        return {'exists': False}
    before = path.stat()
    need(stat.S_ISREG(before.st_mode), f'not a regular file: {path.name}')
    need(before.st_size <= MAX_INPUT, f'input exceeds 256 MiB: {path.name}')
    sha = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            sha.update(chunk)
    after = path.stat()
    need((before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) ==
         (after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode), f'input changed while hashing: {path.name}')
    return {'sha256': sha.hexdigest(), 'size': after.st_size, 'mode': stat.S_IMODE(after.st_mode)}


def inventory(root, paths, excludes=(), state_dir=None, files_only=False):
    omitted = [local_path(root, p).resolve() for p in excludes]
    result = {}

    def add(path):
        if state_dir and path.resolve().is_relative_to(state_dir):
            return
        if any(path.resolve().is_relative_to(p) for p in omitted):
            return
        need(not path.is_symlink(), f'symlink input: {path}')
        key = path.relative_to(root).as_posix()
        if path.is_dir():
            need(not files_only, f'criteria must be explicit files: {key}')
            result[key + '/'] = {'directory': True}
            for child in sorted(path.iterdir()):
                add(child)
        else:
            need(not files_only or path.is_file(), f'missing protected criterion: {key}')
            result[key] = file_stamp(path)
        need(len(result) <= 100000, 'input inventory exceeds 100000 entries')

    for value in paths:
        path = local_path(root, value)
        need(not state_dir or not path.resolve().is_relative_to(state_dir), 'proof state cannot be a product input')
        add(path)
    need(bool(result) or not paths, 'all declared inputs were excluded')
    return result


def redact(value):
    result = str(value)
    for key, secret in os.environ.items():
        if SENSITIVE.search(key) and len(secret) >= 8:
            result = result.replace(secret, '[REDACTED]')
    return result


def observed(status, summary, evidence):
    return {'status': status, 'summary': summary, 'evidence': evidence}


def command_check(check, root):
    cwd = local_path(root, check.get('cwd', '.'))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for name, source in check.get('env_from', {}).items():
        need(source in os.environ, f'missing environment variable: {source}')
        env[name] = os.environ[source]
    limit = check.get('max_bytes', MAX_OUTPUT)
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    hashes = {k: hashlib.sha256() for k in buffers}
    counts = {k: 0 for k in buffers}
    failure = None
    with subprocess.Popen(check['argv'], cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as proc:
        try:
            with selectors.DefaultSelector() as selector:
                for key in buffers:
                    stream = getattr(proc, key)
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, key)
                deadline = time.monotonic() + check.get('timeout', 120)
                while selector.get_map() or proc.poll() is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        failure = 'command timed out'
                        break
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        counts[key.data] += len(chunk)
                        hashes[key.data].update(chunk)
                        buffers[key.data].extend(chunk)
                        if sum(counts.values()) > limit:
                            failure = 'command output limit exceeded'
                            break
                    if failure:
                        break
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        output = {k: v.decode('utf-8', errors='replace') for k, v in buffers.items()}
        evidence = {'argv': [redact(x) for x in check['argv']], 'cwd': str(cwd),
                    'expected_exit': check['expect_exit'], 'actual_exit': proc.returncode,
                    'bytes': counts, 'output_sha256': {k: v.hexdigest() for k, v in hashes.items()},
                    **{k: redact(v[-4000:]) for k, v in output.items()}}
        if failure:
            return observed('FAIL', failure, evidence)
        if proc.returncode != check['expect_exit']:
            return observed('FAIL', f'exit {proc.returncode}, expected {check["expect_exit"]}', evidence)
        if 'stdout_contains' in check and check['stdout_contains'] not in output['stdout']:
            return observed('FAIL', 'stdout expectation not met', evidence)
        return observed('PASS', f'exit {proc.returncode}', evidence)


def file_check(check, root):
    path = local_path(root, check['path'])
    actual = file_stamp(path)
    expected_exists = check.get('exists', True)
    evidence = {'path': check['path'], 'actual': actual,
                'expected': {k: v for k, v in check.items() if k in ('exists', 'contains', 'equals', 'sha256')}}
    if path.exists() != expected_exists:
        return observed('FAIL', 'file existence mismatch', evidence)
    if not expected_exists:
        return observed('PASS', 'file absent as expected', evidence)
    if 'sha256' in check and check['sha256'] != actual['sha256']:
        return observed('FAIL', 'file hash mismatch', evidence)
    if 'contains' in check or 'equals' in check:
        with path.open('rb') as stream:
            data = stream.read(check.get('max_bytes', MAX_OUTPUT) + 1)
        need(len(data) <= check.get('max_bytes', MAX_OUTPUT), 'file observation limit exceeded')
        content = data.decode('utf-8')
        evidence['sample'] = redact(content[-1200:])
        if ('contains' in check and check['contains'] not in content) or ('equals' in check and check['equals'] != content):
            return observed('FAIL', 'file content mismatch', evidence)
    return observed('PASS', 'file expectation met', evidence)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_check(check, root):
    headers = dict(check.get('headers', {}))
    for key, source in check.get('headers_env', {}).items():
        need(source in os.environ, f'missing environment variable: {source}')
        headers[key] = os.environ[source]
    request = urllib.request.Request(check['url'], method=check.get('method', 'GET'), headers=headers)
    deadline = time.monotonic() + check.get('timeout', 15)
    try:
        response = urllib.request.build_opener(NoRedirect).open(request, timeout=check.get('timeout', 15))
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        data = bytearray()
        limit = check.get('max_bytes', MAX_OUTPUT)
        while True:
            need(time.monotonic() < deadline, 'HTTP observation timed out')
            chunk = response.read1(min(65536, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            need(len(data) <= limit, 'HTTP observation limit exceeded')
        body = data.decode('utf-8', errors='replace')
        expected_headers = check.get('expect_headers', {})
        actual_headers = {k: response.headers.get(k) for k in expected_headers}
        evidence = {'url': redact(check['url']), 'status': response.status, 'expected_status': check['expect_status'],
                    'headers': {k: '[REDACTED]' if SENSITIVE.search(k) else redact(v) for k, v in actual_headers.items()},
                    'expected_headers': {k: '[REDACTED]' if SENSITIVE.search(k) else v for k, v in expected_headers.items()},
                    'body_sha256': hashlib.sha256(data).hexdigest(), 'body': redact(body[-1200:]), 'observed_at': time.time_ns()}
        ok = response.status == check['expect_status']
        ok = ok and all(actual_headers[k] == v for k, v in expected_headers.items())
        ok = ok and ('response_contains' not in check or check['response_contains'] in body)
        return observed('PASS' if ok else 'FAIL', f'HTTP {response.status}', evidence)


CHECKERS = {'command': command_check, 'file': file_check, 'http': http_check}


class Task:
    def __init__(self, path):
        self.path = path.resolve()
        self.folder = self.path.parent
        self.contract = load(self.path)
        self.gates = validate(self.contract)
        self.root = (self.folder / self.contract['root']).resolve()
        need(self.root.is_dir(), 'root directory is missing')
        self.state_path = self.folder / 'state.json'
        self.binding = digest({'contract': str(self.path), 'root': str(self.root), 'task_id': self.contract['task_id']})
        self.state = None

    def plans(self, contract=None):
        c = contract or self.contract
        paths = ([c['plan_path']] if 'plan_path' in c else []) + c.get('plan_additions', [])
        return inventory(self.root, paths, files_only=True)

    def criteria(self, contract=None):
        c = contract or self.contract
        return {g['id']: inventory(self.root, g['criteria'], files_only=True) for g in c['gates']}

    def inputs(self, gid):
        gate = self.gates[gid]
        result = inventory(self.root, gate['inputs'], gate.get('excludes', []), self.folder)
        observed_files = [c['path'] for c in gate['checks'] if c['type'] == 'file']
        result.update(inventory(self.root, observed_files, state_dir=self.folder))
        return result

    def runtime(self, gid):
        checks = self.gates[gid]['checks']
        sources = {source for check in checks for field in ('env_from', 'headers_env')
                   for source in check.get(field, {}).values()}
        environment = {}
        for source in sorted(sources):
            need(source in os.environ, f'missing environment variable: {source}')
            environment[source] = digest(os.environ[source])
        executables = {}
        for check in checks:
            if check['type'] == 'command':
                name = check['argv'][0]
                cwd = local_path(self.root, check.get('cwd', '.'))
                path = str(cwd / name) if '/' in name and not Path(name).is_absolute() else name
                search_path = os.environ.get(check.get('env_from', {}).get('PATH', 'PATH'))
                resolved = shutil.which(path, path=search_path)
                executables[check['id']] = {'path': resolved, 'file': file_stamp(Path(resolved).resolve()) if resolved else None}
        return {'engine': file_stamp(Path(__file__).resolve()), 'python': sys.version,
                'python_executable': str(Path(sys.executable).resolve()),
                'environment': environment, 'executables': executables}

    def load_state(self, extending=False):
        need(self.state_path.is_file(), 'contract is not locked (2.2 state is not reusable)')
        s = load(self.state_path)
        object_fields(s, 'schema_version binding contract_sha256 snapshot revision sequence plans criteria records created_at extension_sequence finalized'.split(),
                      'schema_version binding contract_sha256 snapshot revision sequence plans criteria records created_at extension_sequence'.split(), 'state')
        need(s['schema_version'] == SCHEMA and s['binding'] == self.binding, 'state belongs to another contract/task')
        need(digest(s['snapshot']) == s['contract_sha256'], 'state contract snapshot is corrupt')
        need(type(s['revision']) is int and s['revision'] >= 1 and type(s['sequence']) is int and s['sequence'] >= 0, 'corrupt revision/sequence')
        need(isinstance(s['records'], dict) and isinstance(s['criteria'], dict) and isinstance(s['plans'], dict), 'corrupt state records')
        need(extending or s['contract_sha256'] == digest(self.contract), 'contract changed after lock')
        old = s['snapshot']
        need(s['plans'] == self.plans(old), 'original plan or additions changed after lock')
        need(s['criteria'] == self.criteria(old), 'protected criteria changed after lock')
        self.state = s

    def persist(self):
        save(self.state_path, self.state)

    def invalidate_completion(self):
        save(self.folder / 'completion.json', {'status': 'INVALIDATED', 'task_id': self.contract['task_id']})
        if self.state:
            self.state.pop('finalized', None)

    def lock(self):
        if self.state_path.exists():
            self.load_state()
            return 'LOCKED', 0
        need(not (self.folder / 'lock.json').exists(), '2.2 lock exists; use a new task directory')
        need(not any((self.folder / name).exists() for name in ('revisions', 'proofs', 'coverage.json', 'completion.json')),
             'state is missing but history exists; restore a known-good backup or use a new task directory')
        self.plans()
        self.criteria()
        source = '\n'.join(local_path(self.root, p).read_text(encoding='utf-8') for p in
                           ([self.contract['plan_path']] if 'plan_path' in self.contract else []) + self.contract.get('plan_additions', []))
        for req in self.contract.get('requirements', []):
            need(req['source'] in source, f"{req['id']}: source excerpt not found in preserved plan")
        for gid in self.gates:
            self.inputs(gid)
        self.state = {'schema_version': SCHEMA, 'binding': self.binding, 'snapshot': self.contract,
                      'contract_sha256': digest(self.contract), 'revision': 1, 'sequence': 0,
                      'extension_sequence': 0, 'plans': self.plans(), 'criteria': self.criteria(),
                      'records': {}, 'created_at': time.time_ns()}
        self.invalidate_completion()
        save(self.folder / 'revisions' / '1.json', self.contract)
        self.persist()
        return 'LOCKED', 0

    def invalidate(self, gid):
        affected = {gid}
        while True:
            downstream = {g['id'] for g in self.gates.values() if set(g.get('depends_on', [])) & affected}
            if downstream <= affected:
                break
            affected |= downstream
        for item in affected:
            previous = self.state['records'].get(item)
            if previous:
                self.state['records'][item] = {**previous, 'status': 'STALE'}
        self.invalidate_completion()

    def extend(self):
        self.load_state(extending=True)
        old = self.state['snapshot']
        for key in set(old) | set(self.contract):
            if key not in ('gates', 'requirements', 'mode', 'plan_additions'):
                need(old.get(key) == self.contract.get(key), f'{key} cannot change during extension')
        need(list(LIMITS).index(self.contract['mode']) >= list(LIMITS).index(old['mode']), 'mode cannot be weakened')
        changed = set()
        additions = 0
        for key in ('gates', 'requirements'):
            before = {x['id']: x for x in old.get(key, [])}
            after = {x['id']: x for x in self.contract.get(key, [])}
            need(all(after.get(k) == v for k, v in before.items()), f'existing {key} cannot be changed or removed')
            additions += len(after) - len(before)
            for k in set(after) - set(before):
                changed.add(k if key == 'gates' else after[k]['gate'])
        need(additions > 0, 'extension adds no gates or requirements')
        need(self.contract.get('plan_additions', [])[:len(old.get('plan_additions', []))] == old.get('plan_additions', []), 'plan additions cannot be removed/reordered')
        plans, criteria = self.plans(), self.criteria()
        source = '\n'.join(local_path(self.root, p).read_text(encoding='utf-8') for p in
                           ([self.contract['plan_path']] if 'plan_path' in self.contract else []) + self.contract.get('plan_additions', []))
        for req in self.contract.get('requirements', []):
            need(req['source'] in source, f"{req['id']}: source excerpt missing")
        for gid in self.gates:
            self.inputs(gid)
        self.state['revision'] += 1
        self.state['sequence'] += 1
        self.state['extension_sequence'] = self.state['sequence']
        for gid in changed | {self.contract['final_gate']}:
            self.invalidate(gid)
        self.state.update(snapshot=self.contract, contract_sha256=digest(self.contract), plans=plans, criteria=criteria)
        save(self.folder / 'revisions' / f"{self.state['revision']}.json", self.contract)
        self.persist()
        return 'EXTENDED', 0

    def valid(self, gid, visiting=None):
        visiting = set() if visiting is None else visiting
        need(gid not in visiting, 'corrupt dependency cycle')
        visiting.add(gid)
        record = self.state['records'].get(gid)
        need(isinstance(record, dict) and record.get('status') == 'PASS', f'{gid}: no current PASS')
        need(text(record.get('proof')) and re.fullmatch(r'\d+-[A-Za-z0-9_-]+', record['proof']), 'invalid proof reference')
        proof = load(self.folder / 'proofs' / (record['proof'] + '.json'))
        need(digest(proof) == record.get('sha256'), f'{gid}: evidence is corrupt')
        need(proof.get('status') == 'PASS' and proof.get('gate') == gid and proof.get('definition') == digest(self.gates[gid]), f'{gid}: evidence definition mismatch')
        need(proof.get('binding') == self.binding, f'{gid}: evidence belongs to another task')
        need(proof.get('inputs') == self.inputs(gid), f'{gid}: product inputs changed')
        need(proof.get('criteria') == self.state['criteria'][gid], f'{gid}: criteria revision mismatch')
        need(proof.get('runtime') == self.runtime(gid), f'{gid}: verifier, executable or declared environment changed')
        need(set(proof.get('dependencies', {})) == set(self.gates[gid].get('depends_on', [])), f'{gid}: incomplete dependency evidence')
        for dep, ref in proof['dependencies'].items():
            self.valid(dep, visiting.copy())
            need(self.state['records'][dep]['proof'] == ref, f'{gid}: dependency attempt changed')
        visiting.remove(gid)
        return proof

    def verify(self, target):
        need(target in self.gates, 'known --gate is required')
        self.load_state()
        self.invalidate(target)
        self.persist()
        memo = {}

        def evaluate(gid):
            if gid in memo:
                return memo[gid]
            self.invalidate(gid)
            self.state['sequence'] += 1
            attempt = f"{self.state['sequence']}-{gid}"
            self.state['records'][gid] = {'status': 'RUNNING', 'proof': attempt}
            self.persist()
            proof = {'id': attempt, 'gate': gid, 'binding': self.binding, 'revision': self.state['revision'],
                     'contract_sha256': digest(self.contract), 'definition': digest(self.gates[gid]),
                     'started_at': time.time_ns(), 'status': 'BLOCKED', 'checks': [], 'dependencies': {}}
            try:
                for dep in self.gates[gid].get('depends_on', []):
                    need(evaluate(dep) == 'PASS', f'{gid}: dependency {dep} did not pass')
                    proof['dependencies'][dep] = self.state['records'][dep]['proof']
                proof['inputs'] = self.inputs(gid)
                proof['criteria'] = self.criteria()[gid]
                proof['runtime'] = self.runtime(gid)
                need(self.state['criteria'][gid] == proof['criteria'], 'protected criteria changed')
                proof['status'] = 'PASS'
                for check in self.gates[gid]['checks']:
                    outcome = CHECKERS[check['type']](check, self.root)
                    proof['checks'].append({'id': check['id'], 'purpose': check['purpose'], **outcome})
                    if outcome['status'] != 'PASS':
                        proof['status'] = outcome['status']
                        break
                need(proof['inputs'] == self.inputs(gid), f'{gid}: product changed during verification')
                need(proof['criteria'] == self.criteria()[gid], f'{gid}: criteria changed during verification')
                need(proof['runtime'] == self.runtime(gid), f'{gid}: runtime changed during verification')
                need(self.state['plans'] == self.plans(), 'plan changed during verification')
                for dep in proof['dependencies']:
                    self.valid(dep)
            except KeyboardInterrupt:
                proof['status'] = 'BLOCKED'
                proof['reason'] = 'verification interrupted'
                self.finish(proof)
                raise
            except Exception as exc:
                proof['status'] = 'BLOCKED'
                proof['reason'] = redact(f'{type(exc).__name__}: {exc}')
            self.finish(proof)
            memo[gid] = proof['status']
            return proof['status']

        status = evaluate(target)
        for gid, value in memo.items():
            print(f'{value:7} {gid}')
        return ('GATE_PASS', 0) if status == 'PASS' else ('GATE_FAILED', 1) if status == 'FAIL' else ('BLOCKED', 2)

    def finish(self, proof):
        self.state['sequence'] += 1
        proof['completed_sequence'] = self.state['sequence']
        proof['completed_at'] = time.time_ns()
        save(self.folder / 'proofs' / (proof['id'] + '.json'), proof)
        self.state['records'][proof['gate']] = {'status': proof['status'], 'proof': proof['id'], 'sha256': digest(proof)}
        self.persist()

    def coverage(self):
        self.load_state()
        requirements = self.contract.get('requirements') or [{'id': 'completion', 'text': 'Task outcome', 'gate': self.contract['final_gate'], 'source': ''}]
        matrix, latest = [], 0
        for req in requirements:
            row = dict(req, status='MISSING')
            try:
                proof = self.valid(req['gate'])
                row.update(status='VERIFIED', proof=proof['id'])
                latest = max(latest, proof['completed_sequence'])
            except (Blocked, OSError, ValueError, TypeError, KeyError) as exc:
                row['reason'] = str(exc)
            matrix.append(row)
        final, final_reason = None, None
        try:
            final = self.valid(self.contract['final_gate'])
            need(final['completed_sequence'] >= latest and final['completed_sequence'] > self.state['extension_sequence'], 'final gate must be rerun')
            # External observations must belong to the final dependency closure.
            closure = set()
            def visit(gid):
                closure.add(gid)
                for dep in self.gates[gid].get('depends_on', []):
                    if dep not in closure:
                        visit(dep)
            visit(self.contract['final_gate'])
            need(all(g['id'] in closure for g in self.gates.values() if any(c['type'] == 'http' for c in g['checks'])), 'HTTP observations must be dependencies of the final gate')
        except (Blocked, OSError, ValueError, TypeError, KeyError) as exc:
            final_reason = str(exc)
        covered = sum(row['status'] == 'VERIFIED' for row in matrix)
        success = covered == len(matrix) and final_reason is None
        report = {'schema_version': SCHEMA, 'task_id': self.contract['task_id'], 'revision': self.state['revision'],
                  'contract_sha256': digest(self.contract), 'plans_sha256': digest(self.state['plans']),
                  'status': 'COVERAGE_COMPLETE' if success else 'INCOMPLETE_PLAN_COVERAGE',
                  'coverage': 100 * covered // len(matrix), 'verified': covered, 'total': len(matrix), 'requirements': matrix,
                  'final_proof': final['id'] if final else None, 'final_reason': final_reason}
        report['snapshot'] = digest(report)
        save(self.folder / 'coverage.json', report)
        return report

    def finalize(self, audit_path=None):
        self.invalidate_completion()
        report = self.coverage()
        need(report['status'] == 'COVERAGE_COMPLETE', 'coverage incomplete or evidence stale')
        if self.contract['kind'] == 'plan':
            need(audit_path is not None, 'plan finalization requires --audit')
            audit = load(audit_path)
            object_fields(audit, 'schema_version revision contract_sha256 snapshot plans_sha256 requirements gaps plan_review'.split(),
                          'schema_version revision contract_sha256 snapshot plans_sha256 requirements gaps plan_review'.split(), 'audit')
            for key in ('schema_version', 'revision', 'contract_sha256', 'snapshot', 'plans_sha256'):
                need(audit[key] == report[key], f'audit {key} is stale or incorrect')
            need(audit['gaps'] == [] and text(audit['plan_review']), 'audit reports gaps or lacks whole-plan review')
            need(isinstance(audit['requirements'], list), 'audit requirements must be a list')
            rows = {}
            for item in audit['requirements']:
                object_fields(item, ['id', 'source', 'proof', 'assessment'], ['id', 'source', 'proof', 'assessment'], 'audit requirement')
                need(item['id'] not in rows and text(item['assessment']), 'duplicate audit id or empty assessment')
                rows[item['id']] = item
            need(set(rows) == {r['id'] for r in report['requirements']}, 'audit must review every requirement')
            for req in report['requirements']:
                need(rows[req['id']]['source'] == req['source'] and rows[req['id']]['proof'] == req['proof'], 'audit requirement evidence mismatch')
            save(self.folder / 'audits' / (report['snapshot'] + '.json'), audit)
        need(self.coverage()['snapshot'] == report['snapshot'], 'evidence changed during finalization')
        result = dict(report, status='VERIFIED_SUCCESS', observed_at=time.time_ns(), validity='Only for these contract, input and proof versions; external state is point-in-time.')
        save(self.folder / 'completion.json', result)
        return 'VERIFIED_SUCCESS', 0


def interrupted(signum, frame):
    raise KeyboardInterrupt


def initialize(args):
    need(not args.contract.exists(), 'contract already exists; use lock or extend')
    need(not any((args.contract.parent / name).exists() for name in ('state.json', 'lock.json', 'proofs', 'revisions', 'completion.json', 'coverage.json')),
         'task history already exists; restore its contract or use a new task directory')
    root = Path.cwd().resolve()
    need(args.contract.resolve().is_relative_to(root), 'new task must be inside the project')
    contract = {'schema_version': SCHEMA, 'task_id': args.contract.resolve().parent.name,
                'root': os.path.relpath(root, args.contract.resolve().parent), 'kind': 'task',
                'mode': 'light', 'final_gate': 'final', 'gates': [{
                    'id': 'final', 'level': 'task', 'inputs': args.input, 'criteria': args.criterion,
                    'checks': [{'id': 'acceptance', 'type': 'command', 'purpose': 'behavior',
                                'effect': 'isolated_test', 'argv': args.run, 'expect_exit': 0}]}]}
    need(bool(args.supersedes) == text(args.reason),
         '--supersedes and a nonempty --reason are required together')
    if args.supersedes:
        need(args.supersedes.resolve().is_relative_to(root), 'previous task must be inside the project')
        previous = Task(args.supersedes)
        need(previous.root == root and previous.contract['kind'] == 'task' and previous.contract['mode'] == 'light',
             'init can replace only a light task in the same project; use the full workflow otherwise')
        previous.load_state()
        contract['supersedes'] = {'task_id': previous.contract['task_id'],
                                  'contract_sha256': previous.state['contract_sha256'], 'reason': args.reason}
    validate(contract)
    need(shutil.which(args.run[0]) is not None,
         'executable not found; --run expects separate arguments, e.g. --run python3 acceptance.py')
    inventory(root, args.criterion, files_only=True)
    inventory(root, args.input, state_dir=args.contract.resolve().parent)
    save(args.contract, contract)
    return Task(args.contract).lock()


def main():
    parser = argparse.ArgumentParser(description='DoneProof versioned completion verifier')
    parser.add_argument('--version', action='version', version=VERSION)
    sub = parser.add_subparsers(dest='action', required=True)
    child = sub.add_parser('init', help='create and lock a light task from existing acceptance tests')
    child.add_argument('contract', type=Path)
    child.add_argument('--input', action='append', required=True)
    child.add_argument('--criterion', action='append', required=True)
    child.add_argument('--supersedes', type=Path, help='previous protected light-task contract; kept unchanged')
    child.add_argument('--reason', help='justification for replacing the previous light task')
    child.add_argument('--run', nargs=argparse.REMAINDER, required=True)
    for name in ('lock', 'extend', 'verify', 'coverage', 'finalize'):
        child = sub.add_parser(name)
        child.add_argument('contract', type=Path)
        if name == 'verify':
            child.add_argument('--gate', required=True)
        if name == 'finalize':
            child.add_argument('--audit', type=Path)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.action == 'init':
            need(args.contract.resolve().is_relative_to(Path.cwd().resolve()), 'new task must be inside the project')
        with exclusive(args.contract.resolve().parent):
            if args.action == 'init':
                status, code = initialize(args)
                print(status)
                return code
            task = Task(args.contract)
            if args.action == 'verify':
                status, code = task.verify(args.gate)
            elif args.action == 'coverage':
                report = task.coverage()
                status = f"{report['status']} coverage={report['coverage']}% requirements={report['verified']}/{report['total']}"
                code = 0 if report['status'] == 'COVERAGE_COMPLETE' else 1
            elif args.action == 'finalize':
                status, code = task.finalize(args.audit)
            else:
                status, code = getattr(task, args.action)()
            print(status)
            return code
    except KeyboardInterrupt:
        print('BLOCKED: interrupted; previous evidence cannot approve a started attempt')
        return 2
    except Exception as exc:
        print('BLOCKED: ' + redact(f'{type(exc).__name__}: {exc}'))
        return 2


if __name__ == '__main__':
    sys.exit(main())
