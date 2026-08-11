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


LOCK = Path(".proof-of-done/lock.json")
LEDGER = Path(".proof-of-done/ledger.json")


def load(path):
    return json.loads(Path(path).read_text())


def digest(data):
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def result(status, evidence):
    return {"status": status, "evidence": evidence}


def lock_contract(path):
    contract = load(path)
    sha = digest(contract)

    if LOCK.exists():
        current = load(LOCK)

        if current["sha256"] != sha:
            print("BLOCKED: contract is already locked with different criteria")
            return 2

        print(f"LOCKED {sha}")
        return 0

    save(
        LOCK,
        {
            "contract": str(path),
            "sha256": sha,
            "locked_at": int(time.time()),
        },
    )

    print(f"LOCKED {sha}")
    return 0


def check_command(check):
    argv = check["argv"]

    try:
        proc = subprocess.run(
            argv,
            cwd=check.get("cwd"),
            capture_output=True,
            text=True,
            timeout=check.get("timeout", 120),
        )
    except FileNotFoundError:
        return result("BLOCKED", f"command not found: {argv[0]}")
    except subprocess.TimeoutExpired:
        return result("FAIL", f"command timed out: {' '.join(argv)}")

    expected = check.get("expect_exit", 0)

    if proc.returncode != expected:
        return result(
            "FAIL",
            {
                "argv": argv,
                "expected_exit": expected,
                "actual_exit": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
            },
        )

    expected_text = check.get("stdout_contains")

    if expected_text is not None and expected_text not in proc.stdout:
        return result(
            "FAIL",
            {
                "argv": argv,
                "missing_stdout": expected_text,
                "stdout": proc.stdout[-4000:],
            },
        )

    return result(
        "PASS",
        {
            "argv": argv,
            "exit": proc.returncode,
            "stdout": proc.stdout[-2000:],
        },
    )


def check_file(check):
    path = Path(check["path"])
    expected_exists = check.get("exists", True)

    if path.exists() != expected_exists:
        return result(
            "FAIL",
            {
                "path": str(path),
                "expected_exists": expected_exists,
                "actual_exists": path.exists(),
            },
        )

    if not expected_exists:
        return result("PASS", {"path": str(path), "exists": False})

    needle = check.get("contains")

    if needle is not None:
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            return result("BLOCKED", f"cannot read {path}: {exc}")

        if needle not in content:
            return result(
                "FAIL",
                {
                    "path": str(path),
                    "missing": needle,
                },
            )

    return result("PASS", {"path": str(path), "exists": True})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_http(check):
    body = check.get("body")

    if body is not None:
        body = body.encode()

    request = urllib.request.Request(
        check["url"],
        data=body,
        method=check.get("method", "GET"),
        headers=check.get("headers", {}),
    )

    opener = urllib.request.build_opener(NoRedirect)

    try:
        response = opener.open(
            request,
            timeout=check.get("timeout", 15),
        )
    except urllib.error.HTTPError as exc:
        response = exc
    except urllib.error.URLError as exc:
        return result("BLOCKED", f"HTTP unavailable: {exc}")

    status = response.getcode()
    response_body = response.read().decode(errors="replace")
    expected_status = check.get("expect_status", 200)

    if status != expected_status:
        return result(
            "FAIL",
            {
                "url": check["url"],
                "expected_status": expected_status,
                "actual_status": status,
                "body": response_body[-4000:],
            },
        )

    expected_body = check.get("response_contains")

    if expected_body is not None and expected_body not in response_body:
        return result(
            "FAIL",
            {
                "url": check["url"],
                "missing_response": expected_body,
                "body": response_body[-4000:],
            },
        )

    for name, expected in check.get("expect_headers", {}).items():
        actual = response.headers.get(name)

        if actual != expected:
            return result(
                "FAIL",
                {
                    "url": check["url"],
                    "header": name,
                    "expected": expected,
                    "actual": actual,
                },
            )

    return result(
        "PASS",
        {
            "url": check["url"],
            "status": status,
            "body": response_body[-2000:],
        },
    )


CHECKERS = {
    "command": check_command,
    "file": check_file,
    "http": check_http,
}


def run_check(check):
    checker = CHECKERS.get(check["type"])

    if not checker:
        return result("BLOCKED", f"unknown check type: {check['type']}")

    return checker(check)


def gate_status(checks):
    statuses = [check["status"] for check in checks]

    if not statuses:
        return "BLOCKED"

    if all(status == "PASS" for status in statuses):
        return "PASS"

    if "FAIL" in statuses:
        return "FAIL"

    return "BLOCKED"


def verify(path, target=None):
    contract = load(path)

    if not LOCK.exists():
        print("BLOCKED: success contract is not locked")
        return 2

    lock = load(LOCK)

    if lock["sha256"] != digest(contract):
        print("BLOCKED: success contract changed after lock")
        return 2

    gates = {gate["id"]: gate for gate in contract["gates"]}
    memo = {}
    visiting = set()

    if target and target not in gates:
        print(f"BLOCKED: unknown gate {target}")
        return 2

    def evaluate(gate_id):
        if gate_id in memo:
            return memo[gate_id]

        if gate_id in visiting:
            raise ValueError(f"cyclic gate dependency at {gate_id}")

        visiting.add(gate_id)
        gate = gates[gate_id]

        dependencies = []

        for dep in gate.get("depends_on", []):
            dep_result = evaluate(dep)
            dependencies.append(
                {
                    "id": dep,
                    "status": dep_result["status"],
                }
            )

        if any(dep["status"] != "PASS" for dep in dependencies):
            gate_result = {
                "id": gate_id,
                "level": gate["level"],
                "status": "BLOCKED",
                "dependencies": dependencies,
                "checks": [],
                "evidence": "dependency gate did not pass",
            }
        else:
            checks = []

            for check in gate.get("checks", []):
                observed = run_check(check)

                checks.append(
                    {
                        "id": check["id"],
                        **observed,
                    }
                )

            gate_result = {
                "id": gate_id,
                "level": gate["level"],
                "status": gate_status(checks),
                "dependencies": dependencies,
                "checks": checks,
            }

        visiting.remove(gate_id)
        memo[gate_id] = gate_result
        return gate_result

    try:
        if target:
            targets = [evaluate(target)]
        else:
            targets = [evaluate(gate["id"]) for gate in contract["gates"]]
    except ValueError as exc:
        print(f"BLOCKED: {exc}")
        return 2

    relevant_statuses = [gate["status"] for gate in targets]

    all_results = list(memo.values())

    checks = [
        check
        for gate in all_results
        for check in gate["checks"]
    ]

    passed = sum(check["status"] == "PASS" for check in checks)

    if all(status == "PASS" for status in relevant_statuses):
        overall = "VERIFIED_SUCCESS"
        exit_code = 0
    elif "FAIL" in relevant_statuses:
        overall = "VERIFIED_PARTIAL" if passed else "FAILED"
        exit_code = 1
    elif passed:
        overall = "VERIFIED_PARTIAL"
        exit_code = 1
    else:
        overall = "BLOCKED"
        exit_code = 2

    ledger = {
        "version": 2,
        "contract_sha256": digest(contract),
        "verified_at": int(time.time()),
        "target": target,
        "status": overall,
        "gates": all_results,
    }

    save(LEDGER, ledger)

    print(overall)

    for gate in all_results:
        print(f"{gate['status']:7} {gate['level']:9} {gate['id']}")

        for check in gate["checks"]:
            print(f"  {check['status']:7} {check['id']}")

    print(f"evidence: {LEDGER}")

    return exit_code


def main():
    parser = argparse.ArgumentParser(description="DoneProof verifier")
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
