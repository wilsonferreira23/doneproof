#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LEDGER_VERSION = 2
STATE_DIR = Path(".proof-of-done")
LOCK = STATE_DIR / "lock.json"
LEDGER = STATE_DIR / "ledger.json"
MODE_LIMITS = {"light": 4, "standard": 7, "strict": 12}
EVIDENCE_LIMIT = 1200


def load(path):
    return json.loads(Path(path).read_text())


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def digest(data):
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def trim(value, limit=EVIDENCE_LIMIT):
    if value is None:
        return ""
    return str(value)[-limit:]


def result(status, summary, evidence=None):
    return {"status": status, "summary": summary, "evidence": evidence if evidence is not None else summary}


def lock_contract(path):
    contract = load(path)
    error = validate_contract(contract)
    if error:
        print(f"BLOCKED: {error}")
        return 2
    sha = digest(contract)
    if LOCK.exists():
        current = load(LOCK)
        if current.get("sha256") != sha:
            print("BLOCKED: a different success contract is already locked")
            return 2
        print(f"LOCKED {sha[:12]}")
        return 0
    save(LOCK, {"version": LEDGER_VERSION, "contract": str(path), "sha256": sha, "locked_at": int(time.time())})
    print(f"LOCKED {sha[:12]}")
    return 0


def check_command(check):
    argv = check.get("argv")
    if not isinstance(argv, list) or not argv:
        return result("BLOCKED", "invalid command argv")
    try:
        proc = subprocess.run(argv, cwd=check.get("cwd"), capture_output=True, text=True, timeout=check.get("timeout", 120))
    except FileNotFoundError:
        return result("BLOCKED", f"command not found: {argv[0]}")
    except subprocess.TimeoutExpired:
        return result("FAIL", f"command timed out: {' '.join(argv)}")
    expected = check.get("expect_exit", 0)
    evidence = {"argv": argv, "expected_exit": expected, "actual_exit": proc.returncode, "stdout": trim(proc.stdout), "stderr": trim(proc.stderr)}
    if proc.returncode != expected:
        return result("FAIL", f"exit {proc.returncode}, expected {expected}", evidence)
    needle = check.get("stdout_contains")
    if needle is not None and needle not in proc.stdout:
        return result("FAIL", f"stdout missing: {needle!r}", evidence)
    return result("PASS", f"exit {proc.returncode}", evidence)


def check_file(check):
    path = Path(check["path"])
    expected_exists = check.get("exists", True)
    actual_exists = path.exists()
    if actual_exists != expected_exists:
        return result("FAIL", f"{path}: exists={actual_exists}, expected={expected_exists}", {"path": str(path), "exists": actual_exists})
    if not expected_exists:
        return result("PASS", f"{path}: absent as expected")
    needle = check.get("contains")
    if needle is not None:
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            return result("BLOCKED", f"cannot read {path}: {exc}")
        if needle not in content:
            return result("FAIL", f"{path}: expected text not found")
    return result("PASS", f"{path}: verified")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_http(check):
    body = check.get("body")
    if body is not None:
        body = body.encode()
    request = urllib.request.Request(check["url"], data=body, method=check.get("method", "GET"), headers=check.get("headers", {}))
    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=check.get("timeout", 15))
    except urllib.error.HTTPError as exc:
        response = exc
    except urllib.error.URLError as exc:
        return result("BLOCKED", f"HTTP unavailable: {exc.reason}")
    status = response.getcode()
    response_body = response.read().decode(errors="replace")
    expected = check.get("expect_status", 200)
    evidence = {"url": check["url"], "status": status, "body": trim(response_body)}
    if status != expected:
        return result("FAIL", f"HTTP {status}, expected {expected}", evidence)
    needle = check.get("response_contains")
    if needle is not None and needle not in response_body:
        return result("FAIL", f"response missing: {needle!r}", evidence)
    for name, expected_value in check.get("expect_headers", {}).items():
        actual = response.headers.get(name)
        if actual != expected_value:
            return result("FAIL", f"header {name}={actual!r}, expected {expected_value!r}", evidence)
    return result("PASS", f"HTTP {status}", evidence)


CHECKERS = {"command": check_command, "file": check_file, "http": check_http}


def validate_contract(contract):
    if not isinstance(contract, dict):
        return "contract must be a JSON object"
    mode = str(contract.get("mode", "light")).lower()
    if mode not in MODE_LIMITS:
        return f"unknown mode '{mode}'"
    gates = contract.get("gates")
    if not isinstance(gates, list) or not gates:
        return "contract must contain at least one gate"
    seen = set()
    limit = MODE_LIMITS[mode]
    valid_levels = {"task", "feature", "milestone"}
    for gate in gates:
        if not isinstance(gate, dict):
            return "every gate must be an object"
        gate_id = gate.get("id")
        if not isinstance(gate_id, str) or not gate_id:
            return "every gate needs an id"
        if gate_id in seen:
            return f"duplicate gate id '{gate_id}'"
        seen.add(gate_id)
        if gate.get("level") not in valid_levels:
            return f"gate '{gate_id}' has invalid level"
        checks = gate.get("checks")
        if not isinstance(checks, list) or not checks:
            return f"gate '{gate_id}' has no checks"
        if len(checks) > limit:
            return f"gate '{gate_id}' has {len(checks)} checks; {mode} mode allows at most {limit}"
        check_ids = set()
        for check in checks:
            if not isinstance(check, dict):
                return f"gate '{gate_id}' has an invalid check"
            check_id = check.get("id")
            if not isinstance(check_id, str) or not check_id:
                return f"gate '{gate_id}' has a check without id"
            if check_id in check_ids:
                return f"gate '{gate_id}' has duplicate check id '{check_id}'"
            check_ids.add(check_id)
            check_type = check.get("type")
            if not isinstance(check_type, str) or check_type not in CHECKERS:
                return f"check '{check_id}' has unsupported type"
            if check_type == "command":
                if not isinstance(check.get("argv"), list) or not check["argv"] or not all(isinstance(arg, str) and arg for arg in check["argv"]):
                    return f"command check '{check_id}' needs a non-empty argv"
                if "cwd" in check and not isinstance(check["cwd"], str):
                    return f"command check '{check_id}' cwd must be text"
                if "stdout_contains" in check and not isinstance(check["stdout_contains"], str):
                    return f"command check '{check_id}' stdout_contains must be text"
            if check_type == "file":
                if not isinstance(check.get("path"), str) or not check["path"]:
                    return f"file check '{check_id}' needs a path"
                if "contains" in check and not isinstance(check["contains"], str):
                    return f"file check '{check_id}' contains must be text"
            if check_type == "http":
                if not isinstance(check.get("url"), str) or not check["url"]:
                    return f"http check '{check_id}' needs a url"
                if "method" in check and not isinstance(check["method"], str):
                    return f"http check '{check_id}' method must be text"
                if "headers" in check and not isinstance(check["headers"], dict):
                    return f"http check '{check_id}' headers must be an object"
                if "expect_headers" in check and not isinstance(check["expect_headers"], dict):
                    return f"http check '{check_id}' expect_headers must be an object"
                if "body" in check and not isinstance(check["body"], str):
                    return f"http check '{check_id}' body must be text"
                if "response_contains" in check and not isinstance(check["response_contains"], str):
                    return f"http check '{check_id}' response_contains must be text"
    for gate in gates:
        dependencies = gate.get("depends_on", [])
        if not isinstance(dependencies, list):
            return f"gate '{gate['id']}' depends_on must be a list"
        for dep in dependencies:
            if not isinstance(dep, str) or dep not in seen:
                return f"gate '{gate['id']}' depends on unknown gate '{dep}'"
    return None


def verify(path, target):
    contract = load(path)
    error = validate_contract(contract)
    if error:
        print(f"BLOCKED: {error}")
        return 2
    if not target:
        print("BLOCKED: --gate is required to avoid broad verification")
        return 2
    if not LOCK.exists():
        print("BLOCKED: success contract is not locked")
        return 2
    if load(LOCK).get("sha256") != digest(contract):
        print("BLOCKED: success contract changed after lock")
        return 2
    gates = {gate["id"]: gate for gate in contract["gates"]}
    if target not in gates:
        print(f"BLOCKED: unknown gate '{target}'")
        return 2
    memo = {}
    visiting = set()

    def evaluate(gate_id):
        if gate_id in memo:
            return memo[gate_id]
        if gate_id in visiting:
            raise ValueError(f"cyclic gate dependency at '{gate_id}'")
        visiting.add(gate_id)
        gate = gates[gate_id]
        dependencies = []
        for dep in gate.get("depends_on", []):
            dep_result = evaluate(dep)
            dependencies.append({"id": dep, "status": dep_result["status"]})
        if any(dep["status"] != "PASS" for dep in dependencies):
            gate_result = {"id": gate_id, "level": gate["level"], "status": "BLOCKED", "dependencies": dependencies, "checks": [], "summary": "dependency gate did not pass"}
        else:
            checks = []
            status = "PASS"
            for check in gate["checks"]:
                observed = CHECKERS[check["type"]](check)
                checks.append({"id": check["id"], **observed})
                if observed["status"] != "PASS":
                    status = "FAIL" if observed["status"] == "FAIL" else "BLOCKED"
                    break
            gate_result = {"id": gate_id, "level": gate["level"], "status": status, "dependencies": dependencies, "checks": checks}
        visiting.remove(gate_id)
        memo[gate_id] = gate_result
        return gate_result

    try:
        target_result = evaluate(target)
    except ValueError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    checks = [check for gate in memo.values() for check in gate.get("checks", [])]
    passed = sum(check["status"] == "PASS" for check in checks)
    gate_status = target_result["status"]
    if gate_status == "PASS":
        overall, exit_code = "VERIFIED_SUCCESS", 0
    elif gate_status == "FAIL":
        overall, exit_code = ("VERIFIED_PARTIAL" if passed else "FAILED"), 1
    else:
        overall, exit_code = ("VERIFIED_PARTIAL" if passed else "BLOCKED"), 2
    ledger = {"version": LEDGER_VERSION, "mode": contract.get("mode", "light"), "contract_sha256": digest(contract), "verified_at": int(time.time()), "target": target, "status": overall, "gates": list(memo.values())}
    save(LEDGER, ledger)
    print(f"{overall} gate={target}")
    for gate in memo.values():
        print(f"{gate['status']:7} {gate['level']:9} {gate['id']}")
        for check in gate.get("checks", []):
            print(f"  {check['status']:7} {check['id']}: {check['summary']}")
    print(f"ledger={LEDGER}")
    return exit_code


def main():
    parser = argparse.ArgumentParser(description="DoneProof deterministic verifier")
    parser.add_argument("--version", action="version", version="DoneProof")
    sub = parser.add_subparsers(dest="command", required=True)
    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("contract")
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("contract")
    verify_parser.add_argument("--gate")
    args = parser.parse_args()
    if args.command == "lock":
        return lock_contract(args.contract)
    return verify(args.contract, args.gate)


if __name__ == "__main__":
    sys.exit(main())
