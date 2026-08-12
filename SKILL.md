---
name: doneproof
description: Minimal deterministic completion gate for coding agents and looping engineering. Use before claiming implementation work is done. Requires a locked success contract, targeted verification, repair on failure, and real evidence instead of agent confidence.
---

# DoneProof 2.1

The agent does not decide that work is done. Evidence does.

## Default mode: LIGHT

Use the cheapest proof that directly verifies the requested outcome.

- `light`: default; small tasks; max 4 checks per gate.
- `standard`: feature boundaries or meaningful integration; max 7 checks.
- `strict`: auth, permissions, money, migrations, destructive operations, or other high-risk work; max 12 checks.

Do not use `standard` or `strict` just because they sound safer.

## Minimal Success Contract

Before non-trivial implementation, create `.proof-of-done/contract.json` and lock it.

Usually use 2-4 checks for a task. The contract must prove:

1. the requested behavior/output actually works;
2. if persistent/external state changed: read it back and compare;
3. the smallest relevant regression check still passes.

Prefer behavior, API/DB state, tests, and runtime evidence over file existence or source inspection.

Lock before implementation:

    python3 <skill-dir>/scripts/pod.py lock .proof-of-done/contract.json

Do not weaken or replace a locked contract because implementation failed.

## Loop Protocol

For each task:

    implement -> verify targeted task gate -> PASS: continue
                                      -> FAIL: repair -> verify same gate

Use only the gate for the current task. Do not run broad suites on every loop.

After the last task in a feature, run its feature gate.
Run a milestone gate only at a real checkpoint.

If the same gate fails after 3 reasonable repair attempts without materially new evidence, stop thrashing and report the failure/blocker.

## Verification Rules

- A successful write/tool call is not proof of final state.
- Another agent's summary is not proof.
- Reasoning is not proof.
- Mutations require write -> read-back -> compare.
- Bug fixes should reproduce the original failure when practical.
- Do not paste large logs into context. Use the concise CLI result; inspect the ledger only when debugging.
- Never advance the loop on `FAILED`, `BLOCKED`, or `VERIFIED_PARTIAL`.

Verify:

    python3 <skill-dir>/scripts/pod.py verify .proof-of-done/contract.json --gate <gate-id>

The verifier is fail-fast by default and stores detailed evidence in `.proof-of-done/ledger.json`.

## Completion

Only `VERIFIED_SUCCESS` permits a completion claim.

Otherwise report the real status and the smallest useful failure summary.
