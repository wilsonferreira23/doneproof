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

VERSION = "2.2.0"
STATE_DIR = Path(".proof-of-done")
LOCK = STATE_DIR / "lock.json"
LEDGER = STATE_DIR / "ledger.json"
HISTORY = STATE_DIR / "history.json"
COVERAGE = STATE_DIR / "coverage.json"
MODE_LIMITS = {"light": 4, "standard": 7, "strict": 12}
MODE_RANK = {"light": 0, "standard": 1, "strict": 2}
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


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trim(value, limit=EVIDENCE_LIMIT):
    if value is None:
        return ""
    return str(value)[-limit:]


def result(status, summary, evidence=None):
    return {"status": status, "summary": summary, "evidence": evidence if evidence is not None else summary}


def plan_hash(contract):
    plan_path = contract.get("plan_path")
    if not plan_path:
        return None
    path = Path(plan_path)
    if not path.is_file():
        raise FileNotFoundError(plan_path)
    return file_digest(path)


def validate_contract(contract, coverage_required=False):
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
            if check_type not in {"command", "file", "http"}:
                return f"check '{check_id}' has unsupported type"
            if check_type == "command":
                argv = check.get("argv")
                if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
                    return f"command check '{check_id}' needs a non-empty argv"
            elif check_type == "file":
                if not isinstance(check.get("path"), str) or not check["path"]:
                    return f"file check '{check_id}' needs a path"
            elif check_type == "http":
                if not isinstance(check.get("url"), str) or not check["url"]:
                    return f"http check '{check_id}' needs a url"

    for gate in gates:
        deps = gate.get("depends_on", [])
        if not isinstance(deps, list):
            return f"gate '{gate['id']}' depends_on must be a list"
        for dep in deps:
            if dep not in seen:
                return f"gate '{gate['id']}' depends on unknown gate '{dep}'"

    requirements = contract.get("requirements")
    if requirements is not None:
        if not isinstance(requirements, list) or not requirements:
            return "requirements must be a non-empty list"
        req_seen = set()
        for req in requirements:
            if not isinstance(req, dict):
                return "every requirement must be an object"
            req_id = req.get("id")
            text = req.get("text")
            gate_id = req.get("gate")
            if not isinstance(req_id, str) or not req_id:
                return "every requirement needs an id"
            if req_id in req_seen:
                return f"duplicate requirement id '{req_id}'"
            req_seen.add(req_id)
            if not isinstance(text, str) or not text.strip():
                return f"requirement '{req_id}' needs text"
            if gate_id not in seen:
                return f"requirement '{req_id}' maps to unknown gate '{gate_id}'"

    final_gate = contract.get("final_gate")
    if final_gate is not None and final_gate not in seen:
        return f"final_gate '{final_gate}' does not exist"

    if coverage_required:
        if not requirements:
            return "coverage requires a requirements list"
        if not final_gate:
            return "coverage requires final_gate"

    plan_path = contract.get("plan_path")
    if plan_path is not None and (not isinstance(plan_path, str) or not plan_path):
        return "plan_path must be text"

    return None


def check_locked_contract(contract):
    if not LOCK.exists():
        return "success contract is not locked"
    lock = load(LOCK)
    if lock.get("sha256") != digest(contract):
        return "success contract changed after lock"
    expected_plan = lock.get("plan_sha256")
    if expected_plan:
        try:
            actual_plan = plan_hash(contract)
        except FileNotFoundError:
            return f"plan file missing: {contract.get('plan_path')}"
        if actual_plan != expected_plan:
            return "original plan changed after lock"
    return None


def lock_contract(path):
    contract = load(path)
    error = validate_contract(contract)
    if error:
        print(f"BLOCKED: {error}")
        return 2
    try:
        p_hash = plan_hash(contract)
    except FileNotFoundError:
        print(f"BLOCKED: plan file missing: {contract.get('plan_path')}")
        return 2

    sha = digest(contract)
    if LOCK.exists():
        current = load(LOCK)
        if current.get("sha256") != sha:
            print("BLOCKED: a different success contract is already locked")
            return 2
        print(f"LOCKED {sha[:12]}")
        return 0

    save(LOCK, {
        "version": VERSION,
        "contract": str(path),
        "sha256": sha,
        "plan_sha256": p_hash,
        "snapshot": contract,
        "locked_at": time.time_ns(),
    })
    print(f"LOCKED {sha[:12]}")
    return 0


def extend_contract(path):
    if not LOCK.exists():
        print("BLOCKED: no locked contract to extend")
        return 2
    new = load(path)
    error = validate_contract(new)
    if error:
        print(f"BLOCKED: {error}")
        return 2

    lock = load(LOCK)
    old = lock.get("snapshot")
    if not isinstance(old, dict):
        print("BLOCKED: existing lock has no snapshot; create a fresh 2.2 lock")
        return 2

    if old.get("plan_path") != new.get("plan_path"):
        print("BLOCKED: plan_path cannot change during extension")
        return 2
    if old.get("final_gate") != new.get("final_gate"):
        print("BLOCKED: final_gate cannot change during extension")
        return 2
    old_mode = str(old.get("mode", "light")).lower()
    new_mode = str(new.get("mode", "light")).lower()
    if MODE_RANK[new_mode] < MODE_RANK[old_mode]:
        print("BLOCKED: verification mode cannot be weakened")
        return 2

    old_gates = {g["id"]: g for g in old.get("gates", [])}
    new_gates = {g["id"]: g for g in new.get("gates", [])}
    for gate_id, gate in old_gates.items():
        if new_gates.get(gate_id) != gate:
            print(f"BLOCKED: existing gate '{gate_id}' cannot be changed")
            return 2

    old_reqs = {r["id"]: r for r in old.get("requirements", [])}
    new_reqs = {r["id"]: r for r in new.get("requirements", [])}
    for req_id, req in old_reqs.items():
        if new_reqs.get(req_id) != req:
            print(f"BLOCKED: existing requirement '{req_id}' cannot be changed")
            return 2

    if len(new_gates) == len(old_gates) and len(new_reqs) == len(old_reqs):
        print("BLOCKED: extension adds no gates or requirements")
        return 2

    try:
        p_hash = plan_hash(new)
    except FileNotFoundError:
        print(f"BLOCKED: plan file missing: {new.get('plan_path')}")
        return 2
    if lock.get("plan_sha256") != p_hash:
        print("BLOCKED: original plan changed after lock")
        return 2

    new_sha = digest(new)
    lock.update({
        "version": VERSION,
        "sha256": new_sha,
        "snapshot": new,
        "extended_at": time.time_ns(),
    })
    save(LOCK, lock)

    if HISTORY.exists():
        history = load(HISTORY)
        history["contract_sha256"] = new_sha
        save(HISTORY, history)

    print(f"EXTENDED {new_sha[:12]} +{len(new_reqs)-len(old_reqs)} requirements +{len(new_gates)-len(old_gates)} gates")
    return 0


def check_command(check):
    argv = check.get("argv")
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
        return result("FAIL", f"{path}: exists={actual_exists}, expected={expected_exists}")
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


def update_history(contract, gate_results, verified_at):
    sha = digest(contract)
    if HISTORY.exists():
        history = load(HISTORY)
        if history.get("contract_sha256") != sha:
            history = {"version": VERSION, "contract_sha256": sha, "gates": {}}
    else:
        history = {"version": VERSION, "contract_sha256": sha, "gates": {}}
    for gate in gate_results:
        history["gates"][gate["id"]] = {
            "status": gate["status"],
            "verified_at": verified_at,
            "level": gate["level"],
        }
    save(HISTORY, history)


def verify(path, target):
    contract = load(path)
    error = validate_contract(contract)
    if error:
        print(f"BLOCKED: {error}")
        return 2
    if not target:
        print("BLOCKED: --gate is required to avoid broad verification")
        return 2
    lock_error = check_locked_contract(contract)
    if lock_error:
        print(f"BLOCKED: {lock_error}")
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

    now = time.time_ns()
    results = list(memo.values())
    ledger = {"version": VERSION, "mode": contract.get("mode", "light"), "contract_sha256": digest(contract), "verified_at": now, "target": target, "status": overall, "gates": results}
    save(LEDGER, ledger)
    update_history(contract, results, now)

    print(f"{overall} gate={target}")
    for gate in results:
        print(f"{gate['status']:7} {gate['level']:9} {gate['id']}")
        for check in gate.get("checks", []):
            print(f"  {check['status']:7} {check['id']}: {check['summary']}")
    print(f"ledger={LEDGER}")
    return exit_code


def coverage(path):
    contract = load(path)
    error = validate_contract(contract, coverage_required=True)
    if error:
        print(f"BLOCKED: {error}")
        return 2
    lock_error = check_locked_contract(contract)
    if lock_error:
        print(f"BLOCKED: {lock_error}")
        return 2
    if not HISTORY.exists():
        print("INCOMPLETE_PLAN_COVERAGE coverage=0% reason=no verified gates")
        return 1

    history = load(HISTORY)
    if history.get("contract_sha256") != digest(contract):
        print("BLOCKED: verification history belongs to a different contract")
        return 2

    gate_history = history.get("gates", {})
    matrix = []
    covered = 0
    latest_requirement_time = 0
    for req in contract["requirements"]:
        record = gate_history.get(req["gate"])
        ok = bool(record and record.get("status") == "PASS")
        if ok:
            covered += 1
            latest_requirement_time = max(latest_requirement_time, int(record.get("verified_at", 0)))
        matrix.append({
            "id": req["id"],
            "text": req["text"],
            "gate": req["gate"],
            "status": "VERIFIED" if ok else "MISSING",
            "verified_at": record.get("verified_at") if record else None,
        })

    final_id = contract["final_gate"]
    final_record = gate_history.get(final_id)
    final_ok = bool(final_record and final_record.get("status") == "PASS")
    final_is_last = final_ok and int(final_record.get("verified_at", 0)) >= latest_requirement_time

    total = len(matrix)
    percent = round((covered / total) * 100) if total else 0
    success = covered == total and final_ok and final_is_last

    report = {
        "version": VERSION,
        "contract_sha256": digest(contract),
        "coverage": percent,
        "requirements_verified": covered,
        "requirements_total": total,
        "final_gate": final_id,
        "final_gate_status": final_record.get("status") if final_record else "MISSING",
        "final_gate_is_latest": final_is_last,
        "status": "VERIFIED_SUCCESS" if success else "INCOMPLETE_PLAN_COVERAGE",
        "requirements": matrix,
    }
    save(COVERAGE, report)

    if success:
        print(f"VERIFIED_SUCCESS coverage=100% requirements={covered}/{total} final_gate={final_id}")
        print(f"coverage={COVERAGE}")
        return 0

    missing = [row["id"] for row in matrix if row["status"] != "VERIFIED"]
    reason = []
    if missing:
        reason.append("missing=" + ",".join(missing[:8]) + ("..." if len(missing) > 8 else ""))
    if not final_ok:
        reason.append(f"final_gate={final_id}:not-pass")
    elif not final_is_last:
        reason.append(f"final_gate={final_id}:rerun-required")
    print(f"INCOMPLETE_PLAN_COVERAGE coverage={percent}% requirements={covered}/{total} {' '.join(reason)}")
    print(f"coverage={COVERAGE}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="DoneProof deterministic verifier")
    parser.add_argument("--version", action="version", version=f"DoneProof {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    lock_parser = sub.add_parser("lock")
    lock_parser.add_argument("contract")

    extend_parser = sub.add_parser("extend")
    extend_parser.add_argument("contract")

    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("contract")
    verify_parser.add_argument("--gate")

    coverage_parser = sub.add_parser("coverage")
    coverage_parser.add_argument("contract")

    args = parser.parse_args()
    if args.command == "lock":
        return lock_contract(args.contract)
    if args.command == "extend":
        return extend_contract(args.contract)
    if args.command == "coverage":
        return coverage(args.contract)
    return verify(args.contract, args.gate)


if __name__ == "__main__":
    sys.exit(main())
