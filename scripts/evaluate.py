#!/usr/bin/env python3
"""Freeze and run paired, externally graded agent evaluations (stdlib only)."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
try:
    import tomllib
except ImportError:
    tomllib = None

CONDITIONS = ('without', 'v22', 'candidate')
ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def read(path):
    return json.loads(path.read_text())


def snapshot(source, dest):
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns('__pycache__', '.git', 'evaluation'))
    return {p.relative_to(dest).as_posix(): sha(p) for p in dest.rglob('*') if p.is_file()}


def freeze(args):
    if tomllib is None:
        raise ValueError('agent evaluation requires Python 3.11+; the verifier supports 3.10+')
    out = args.output.resolve()
    if out.exists():
        raise ValueError('evaluation output already exists; never overwrite a frozen run')
    corpus = read(args.corpus)
    cases = corpus['cases']
    expected = 12 if args.stage == 'pilot' else 60
    if len(cases) != expected or len({c['id'] for c in cases}) != expected:
        raise ValueError(f'{args.stage} requires {expected} distinct task IDs')
    for case in cases:
        if not all(k in case for k in ('id', 'category', 'request', 'files', 'oracle')):
            raise ValueError('case missing raw input or external oracle')
        if not case['id'].replace('-', '').replace('_', '').isalnum():
            raise ValueError('unsafe case ID')
        for path in case['files']:
            if Path(path).is_absolute() or '..' in Path(path).parts:
                raise ValueError('case file leaves workspace')
        compile(case['oracle'], 'oracle', 'exec')
        if args.stage == 'final' and (not case.get('requirement_ids') or len(set(case['requirement_ids'])) != len(case['requirement_ids'])):
            raise ValueError('final cases require distinct explicit requirement_ids')
    config_path = Path.home() / '.codex/config.toml'
    config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    model = args.model or config.get('model')
    if not model:
        raise ValueError('pass --model or configure a default model before freezing')
    out.mkdir(parents=True)
    hashes = {name: snapshot(path, out / 'skills' / name) for name, path in [('v22', args.baseline), ('candidate', ROOT)]}
    save(out / 'corpus.json', corpus)
    shutil.copyfile(__file__, out / 'controller.py')
    disabled = []
    for folder in (Path.home() / '.codex/skills', Path.home() / '.codex/plugins/cache'):
        if folder.exists():
            disabled += [str(p.parent) for p in folder.rglob('SKILL.md')]
    protocol = {'stage': args.stage, 'model': model, 'reasoning': args.reasoning or config.get('model_reasoning_effort', 'medium'),
                'repetitions': 1 if args.stage == 'pilot' else 2, 'conditions': CONDITIONS,
                'tasks': expected, 'corpus_sha256': sha(out / 'corpus.json'), 'skill_hashes': hashes,
                'timeout_seconds': args.timeout, 'disabled_skills': sorted(set(disabled)),
                'created_at': time.time_ns(), 'python': sys.version,
                'controller_sha256': sha(out / 'controller.py'),
                'cli_version': subprocess.check_output([args.codex, '--version'], text=True).strip(),
                'criteria': {'false_successes': 0, 'omissions_on_complete': 0, 'min_correct_completion': .90,
                             'max_false_blocks': .05, 'max_normal_median_token_overhead': .20}}
    save(out / 'protocol.json', protocol)
    save(out / 'response-schema.json', {'type': 'object', 'properties': {'status': {'type': 'string', 'enum': ['complete', 'blocked']},
                                                                      'summary': {'type': 'string'}},
                                       'required': ['status', 'summary'], 'additionalProperties': False})
    print(f'FROZEN stage={args.stage} episodes={expected * protocol["repetitions"] * 3}')


def verify_freeze(out):
    protocol = read(out / 'protocol.json')
    if 'controller_sha256' in protocol:
        if sha(out / 'controller.py') != protocol['controller_sha256'] or sha(Path(__file__)) != protocol['controller_sha256']:
            raise ValueError('controller changed; use the frozen controller.py for this evaluation')
    elif protocol.get('stage') == 'final':
        raise ValueError('final protocol lacks a frozen controller')
    expected = {'pilot': (12, 1), 'final': (60, 2)}.get(protocol.get('stage'))
    if expected != (protocol.get('tasks'), protocol.get('repetitions')):
        raise ValueError('invalid protocol task/repetition count')
    cases = read(out / 'corpus.json')['cases']
    if len(cases) != expected[0] or len({c['id'] for c in cases}) != expected[0]:
        raise ValueError('corpus task count/IDs do not match protocol')
    if sha(out / 'corpus.json') != protocol['corpus_sha256']:
        raise ValueError('frozen corpus changed')
    for name, manifest in protocol['skill_hashes'].items():
        actual = {p.relative_to(out / 'skills' / name).as_posix(): sha(p) for p in (out / 'skills' / name).rglob('*') if p.is_file()}
        if actual != manifest:
            raise ValueError('frozen skill changed: ' + name)
    return protocol


def verify_completion(workspace, case, protocol):
    skill = workspace / 'skill'
    actual = {p.relative_to(skill).as_posix(): sha(p) for p in skill.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual != protocol['skill_hashes']['candidate']:
        return {'valid': False, 'reason': 'executor changed the supplied skill'}
    attempts = []
    for path in workspace.rglob('completion.json'):
        if path.is_relative_to(skill) or not (path.parent / 'contract.json').is_file():
            continue
        try:
            completion = read(path)
            contract = read(path.parent / 'contract.json')
            if completion.get('status') != 'VERIFIED_SUCCESS':
                continue
            if case['category'] == 'plan':
                if contract.get('kind') != 'plan':
                    continue
                plan = (path.parent / contract['root'] / contract['plan_path']).read_text()
                if plan.rstrip('\n') != case['request'].rstrip('\n'):
                    continue
            if case['category'] == 'strict' and contract.get('mode') != 'strict':
                continue
            if case['category'] == 'integration' and contract.get('mode') not in ('standard', 'strict'):
                continue
            argv = [sys.executable, str(skill / 'scripts/pod.py'), 'finalize', str(path.parent / 'contract.json')]
            if contract['kind'] == 'plan':
                argv += ['--audit', str(path.parent / 'audits' / (completion['snapshot'] + '.json'))]
            check = subprocess.run(argv, cwd=workspace, capture_output=True, text=True, timeout=30)
            attempts.append({'contract': str(path.relative_to(workspace)), 'exit': check.returncode, 'output': check.stdout + check.stderr})
            if check.returncode == 0 and 'VERIFIED_SUCCESS' in check.stdout:
                return {'valid': True, 'checks': attempts}
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            attempts.append({'error': str(exc)})
    return {'valid': False, 'reason': 'no current completion proof with the required workflow', 'checks': attempts}


def episode(out, protocol, case, condition, repetition, codex, stop=None):
    if stop is not None and stop.is_set():
        return None
    folder = out / 'episodes' / f"{case['id']}-{condition}-{repetition}"
    if (folder / 'result.json').exists():
        return read(folder / 'result.json')
    if folder.exists():
        raise ValueError('interrupted episode exists; preserve it and record the interruption before retrying')
    workspace = folder / 'workspace'
    workspace.mkdir(parents=True)
    for path, content in case['files'].items():
        target = workspace / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    (workspace / 'REQUEST.md').write_text(case['request'])
    (folder / 'oracle.py').write_text(case['oracle'])
    skill_instruction = 'Use ordinary appropriate tests. Do not use DoneProof or other optional skills.'
    if condition != 'without':
        shutil.copytree(out / 'skills' / condition, workspace / 'skill')
        skill_instruction = 'Use only the DoneProof skill at skill/SKILL.md. Read it before implementation and follow its completion workflow.'
    prompt = ('Complete the request in REQUEST.md in this isolated workspace. Task category: ' + case['category'] + '. ' + skill_instruction +
              ' Modify only this workspace. Use local standard-library tools; no network or external services. '
              'Do not read files outside the workspace or change skill/. '
              'Create your acceptance tests from the request. Report status complete only when every requested outcome is implemented and verified; otherwise report blocked with the real reason.')
    disabled = '[' + ','.join('{path=' + json.dumps(p) + ',enabled=false}' for p in protocol['disabled_skills']) + ']'
    argv = [codex, '-a', 'never', 'exec', '--ephemeral', '--ignore-user-config', '--skip-git-repo-check',
            '-s', 'workspace-write', '-C', str(workspace), '--json', '-m', protocol['model'],
            '-c', 'model_reasoning_effort=' + json.dumps(protocol['reasoning']),
            '-c', 'skills.config=' + disabled, '--output-schema', str(out / 'response-schema.json'),
            '-o', str(folder / 'answer.json'), prompt]
    started = time.monotonic()
    timed_out = False
    interrupted = False
    with (folder / 'events.jsonl').open('w') as stdout, (folder / 'stderr.log').open('w') as stderr:
        proc = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
        while proc.poll() is None:
            interrupted = stop is not None and stop.is_set()
            timed_out = time.monotonic() - started >= protocol['timeout_seconds']
            if interrupted or timed_out:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                break
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    duration = time.monotonic() - started
    events = []
    for line in (folder / 'events.jsonl').read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    usage = next((e['usage'] for e in reversed(events) if e.get('type') == 'turn.completed'), None)
    try:
        answer = read(folder / 'answer.json')
        declared = answer['status'] == 'complete'
    except (OSError, ValueError, KeyError):
        declared = False
    compliance = verify_completion(workspace, case, protocol) if condition == 'candidate' and declared and protocol['stage'] == 'final' else None
    save(folder / 'compliance.json', compliance)
    grading = folder / 'grading'
    shutil.copytree(workspace, grading, symlinks=True, ignore=shutil.ignore_patterns('__pycache__'))
    grade = subprocess.run([sys.executable, str(folder / 'oracle.py'), str(grading)],
                           cwd=grading, capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    save(folder / 'oracle-result.json', {'exit': grade.returncode, 'stdout': grade.stdout, 'stderr': grade.stderr})
    correct = grade.returncode == 0
    try:
        outcomes = json.loads(grade.stdout)['requirements']
    except (ValueError, KeyError, TypeError):
        outcomes = None
    if protocol['stage'] == 'final':
        correct = correct and isinstance(outcomes, dict) and set(outcomes) == set(case['requirement_ids']) and all(v is True for v in outcomes.values())
    result = {'task': case['id'], 'category': case['category'], 'condition': condition, 'repetition': repetition,
              'protocol_sha256': sha(out / 'protocol.json'),
              'declared_complete': declared, 'correct': correct, 'false_success': declared and not correct,
              'false_block': correct and not declared, 'correct_completion': correct and declared,
              'duration_seconds': duration, 'timed_out': timed_out, 'cli_exit': proc.returncode, 'usage': usage,
              'interrupted': interrupted, 'requirements': outcomes,
              'compliance': compliance,
              'infrastructure_error': proc.returncode != 0 and not timed_out and not interrupted,
              'commands': sum(e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'command_execution' for e in events)}
    save(folder / 'result.json', result)
    print(json.dumps({k: result[k] for k in ('task', 'condition', 'correct', 'declared_complete', 'timed_out')}, ensure_ascii=False), flush=True)
    return result


def run(args):
    out = args.output.resolve()
    protocol = verify_freeze(out)
    jobs = [(case, condition, rep) for case in read(out / 'corpus.json')['cases']
            if not args.category or case['category'] == args.category
            for rep in range(protocol['repetitions']) for condition in CONDITIONS]
    random.Random(20260908).shuffle(jobs)
    if args.limit:
        jobs = jobs[:args.limit]
    stop = threading.Event()
    previous = {sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(episode, out, protocol, *job, args.codex, stop) for job in jobs]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result and result['infrastructure_error']:
                        stop.set()
                except BaseException:
                    stop.set()
                    raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if stop.is_set():
        raise ValueError('evaluation interrupted; completed and interrupted evidence retained')


def wilson(events, total):
    if not total:
        return None
    z = 1.959963984540054
    p = events / total
    divisor = 1 + z * z / total
    center = (p + z * z / (2 * total)) / divisor
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / divisor
    return [max(0, center - half), min(1, center + half)]


def report(args):
    out = args.output.resolve()
    protocol = verify_freeze(out)
    rows = [read(p) for p in sorted((out / 'episodes').glob('*/result.json'))]
    categories = {c['id']: c['category'] for c in read(out / 'corpus.json')['cases']}
    requirements = {c['id']: c.get('requirement_ids') for c in read(out / 'corpus.json')['cases']}
    for path in sorted((out / 'episodes').glob('*/result.json')):
        row = read(path)
        if row['category'] != categories.get(row['task']):
            raise ValueError('episode category differs from corpus')
        events = []
        for line in (path.parent / 'events.jsonl').read_text().splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        usage = next((e['usage'] for e in reversed(events) if e.get('type') == 'turn.completed'), None)
        if row['usage'] != usage:
            raise ValueError('episode summary contradicts raw token usage')
        grade = read(path.parent / 'oracle-result.json')
        actual = grade['exit'] == 0
        if protocol['stage'] == 'final':
            try:
                outcomes = json.loads(grade['stdout'])['requirements']
            except (ValueError, KeyError, TypeError):
                outcomes = None
            actual = actual and isinstance(outcomes, dict) and set(outcomes) == set(requirements[row['task']]) and all(v is True for v in outcomes.values())
            if row.get('requirements') != outcomes:
                raise ValueError('per-requirement summary contradicts external oracle')
            if row['condition'] == 'candidate' and row['declared_complete']:
                if row.get('compliance') != read(path.parent / 'compliance.json'):
                    raise ValueError('compliance summary contradicts recorded verification')
        try:
            declared = read(path.parent / 'answer.json')['status'] == 'complete'
        except (OSError, ValueError, KeyError):
            declared = False
        if (row['correct'], row['declared_complete'], row['false_success'], row['false_block'], row['correct_completion']) != (
                actual, declared, declared and not actual, actual and not declared, actual and declared):
            raise ValueError('episode summary contradicts raw grading/answer')
    expected_keys = {(c['id'], cond, rep) for c in read(out / 'corpus.json')['cases']
                     for cond in CONDITIONS for rep in range(protocol['repetitions'])}
    actual_keys = {(r['task'], r['condition'], r['repetition']) for r in rows}
    if not actual_keys <= expected_keys or len(actual_keys) != len(rows):
        raise ValueError('unknown or duplicate evaluation episodes')
    if any(r['protocol_sha256'] != sha(out / 'protocol.json') for r in rows):
        raise ValueError('episode belongs to another protocol revision')
    summary = {}
    for condition in CONDITIONS:
        group = [r for r in rows if r['condition'] == condition]
        n = len(group)
        tasks = {r['task'] for r in group}
        false_tasks = {r['task'] for r in group if r['false_success']}
        summary[condition] = {'episodes': n, 'false_successes': sum(r['false_success'] for r in group),
                              'correct_completion_rate': sum(r['correct_completion'] for r in group) / n if n else None,
                              'false_block_rate': sum(r['false_block'] for r in group) / sum(r['correct'] for r in group) if any(r['correct'] for r in group) else None,
                              'infrastructure_errors': sum(r['infrastructure_error'] for r in group),
                              'timeouts': sum(r['timed_out'] for r in group),
                              'false_success_task_rate_95_wilson': wilson(len(false_tasks), len(tasks)),
                              'median_seconds': statistics.median(r['duration_seconds'] for r in group) if n else None}
    paired = {(r['task'], r['repetition'], r['condition']): r for r in rows}
    overheads = []
    for r in rows:
        if r['condition'] != 'candidate' or r['category'] != 'normal' or not r['usage']:
            continue
        base = paired.get((r['task'], r['repetition'], 'without'))
        if base and base['usage']:
            denominator = base['usage']['input_tokens'] + base['usage']['output_tokens']
            if denominator > 0:
                overheads.append((r['usage']['input_tokens'] + r['usage']['output_tokens']) / denominator - 1)
    median = statistics.median(overheads) if overheads else None
    expected = protocol['tasks'] * protocol['repetitions'] * 3
    candidate = summary['candidate']
    failures = []
    if len(rows) != expected:
        failures.append('incomplete episodes')
    if protocol['stage'] != 'final':
        failures.append('pilot is not final efficacy evidence')
    if any(s['infrastructure_errors'] for s in summary.values()):
        failures.append('infrastructure errors require investigation')
    if any(not r['usage'] for r in rows):
        failures.append('missing measured token usage')
    if any(r.get('interrupted') for r in rows):
        failures.append('interrupted episodes')
    if protocol['stage'] == 'final' and any(r['condition'] == 'candidate' and r['declared_complete'] and not (r.get('compliance') or {}).get('valid') for r in rows):
        failures.append('completion without valid DoneProof workflow evidence')
    if len(overheads) != sum(r['condition'] == 'candidate' and r['category'] == 'normal' for r in rows):
        failures.append('incomplete normal-task token pairs')
    if candidate['false_successes']:
        failures.append('false success observed')
    if candidate['correct_completion_rate'] is None or candidate['correct_completion_rate'] < .9:
        failures.append('correct completion below 90%')
    baselines = [summary[k]['correct_completion_rate'] for k in ('without', 'v22') if summary[k]['correct_completion_rate'] is not None]
    if baselines and (candidate['correct_completion_rate'] or 0) < max(baselines):
        failures.append('correct completion below best baseline')
    if candidate['false_block_rate'] is None or candidate['false_block_rate'] > .05:
        failures.append('false blocks above 5% or unavailable')
    if median is None or median > .20:
        failures.append('normal-task median token overhead above 20% or unavailable')
    result = {'status': 'EVALUATION_PASS' if not failures else 'EVALUATION_INCOMPLETE' if len(rows) != expected else 'EVALUATION_FAILED',
              'episodes': len(rows), 'expected': expected, 'conditions': summary, 'median_normal_token_overhead': median,
              'normal_token_overhead_p95': sorted(overheads)[max(0, math.ceil(.95 * len(overheads)) - 1)] if overheads else None,
              'failures': failures, 'limitations': ['No observed false success is not a guarantee of zero risk.',
                                                  'Wilson interval groups repeated executions by task.',
                                                  'Corpus provenance and oracle quality must be assessed separately.']}
    result['by_category'] = {}
    for category in sorted(set(categories.values())):
        result['by_category'][category] = {}
        for condition in CONDITIONS:
            group = [r for r in rows if r['category'] == category and r['condition'] == condition]
            tokens = sorted(r['usage']['input_tokens'] + r['usage']['output_tokens'] for r in group if r['usage'])
            result['by_category'][category][condition] = {
                'episodes': len(group), 'correct_completions': sum(r['correct_completion'] for r in group),
                'false_successes': sum(r['false_success'] for r in group),
                'median_tokens': statistics.median(tokens) if tokens else None,
                'p95_tokens': tokens[max(0, math.ceil(.95 * len(tokens)) - 1)] if tokens else None,
                'median_commands': statistics.median(r.get('commands', 0) for r in group) if group else None,
                'median_seconds': statistics.median(r['duration_seconds'] for r in group) if group else None}
    save(out / 'report.json', result)
    print(json.dumps(result, indent=2))
    return 1 if args.require_pass and failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    freeze_parser = sub.add_parser('freeze')
    freeze_parser.add_argument('corpus', type=Path)
    freeze_parser.add_argument('output', type=Path)
    freeze_parser.add_argument('--baseline', type=Path, required=True)
    freeze_parser.add_argument('--stage', choices=['pilot', 'final'], required=True)
    freeze_parser.add_argument('--model')
    freeze_parser.add_argument('--reasoning', choices=['low', 'medium', 'high', 'xhigh', 'max'],
                               help='explicit effort for every condition; defaults to saved configuration')
    freeze_parser.add_argument('--timeout', type=int, default=600)
    freeze_parser.add_argument('--codex', default='codex')
    run_parser = sub.add_parser('run')
    run_parser.add_argument('output', type=Path)
    run_parser.add_argument('--workers', type=int, choices=[1, 2, 3], default=3)
    run_parser.add_argument('--limit', type=int)
    run_parser.add_argument('--category', choices=['normal', 'integration', 'strict', 'plan', 'operational'],
                            help='development subset only; incomplete runs never satisfy efficacy')
    run_parser.add_argument('--codex', default='codex')
    report_parser = sub.add_parser('report')
    report_parser.add_argument('output', type=Path)
    report_parser.add_argument('--require-pass', action='store_true')
    args = parser.parse_args()
    try:
        return {'freeze': freeze, 'run': run, 'report': report}[args.command](args) or 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print('EVALUATION_BLOCKED:', str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
