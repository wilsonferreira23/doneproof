#!/usr/bin/env python3
"""Exercise the distributed examples in disposable copies."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POD = ROOT / 'scripts/pod.py'


def call(root, action, *args, success=True):
    proc = subprocess.run([sys.executable, str(POD), action, str(root / '.proof-of-done/contract.json'), *args],
                          cwd=root, capture_output=True, text=True, timeout=30)
    assert (proc.returncode == 0) == success, proc.stdout + proc.stderr
    return proc.stdout


def main():
    for path in [ROOT / 'SKILL.md', ROOT / 'README.md', * (ROOT / 'references').glob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if '://' not in link:
                assert (path.parent / link.split('#')[0]).exists(), link
    for name in ('basic', 'code', 'strict'):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / name
            shutil.copytree(ROOT / 'examples' / name, root)
            contract = json.loads((root / '.proof-of-done/contract.json').read_text())
            call(root, 'lock')
            args = []
            if name == 'strict':
                assert 'AUDIT_REQUIRED' in call(root, 'finish', success=False)
                draft = next((root / '.proof-of-done').glob('audit-draft-*.json'))
                call(root, 'finish', '--audit', str(draft), success=False)
                audit = json.loads(draft.read_text())
                audit.update(gaps=[], plan_review='Example fixture: operator access, guest rejection, persisted readback and their combined flow are each exercised.',
                             requirements=[dict(r, assessment='The distributed acceptance.py assertion for this purpose executed against product.py.') for r in audit['requirements']])
                (root / 'audit.json').write_text(json.dumps(audit))
                args = ['--audit', str(root / 'audit.json')]
            assert 'VERIFIED_SUCCESS' in call(root, 'finish', *args)
            if name == 'strict':
                path = root / 'product.py'
                original = path.read_text()
                path.write_text(original.replace('if role != "operator":', 'if False:'))
                call(root, 'verify', '--gate', 'negative', success=False)
                call(root, 'finalize', *args, success=False)
                path.write_text(original.replace('Path(path).write_text(value)', 'return None'))
                call(root, 'verify', '--gate', 'readback', success=False)
                call(root, 'finalize', *args, success=False)
            elif name == 'code':
                (root / 'app.py').write_text('def greet(name):\n    return "wrong"\n')
                call(root, 'verify', '--gate', 'greeting', success=False)
                call(root, 'finalize', success=False)
            else:
                (root / 'result.txt').write_text('broken')
                call(root, 'verify', '--gate', contract['final_gate'], success=False)
                call(root, 'finalize', success=False)
            print(name + ': positive flow and negative control passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
