---
name: doneproof
description: Deterministic completion gate for coding agents and looping engineering. Use before claiming implementation work is done. Requires a locked success contract, targeted verification, repair on failure, and real evidence instead of agent confidence.
---

# DoneProof

The agent does not decide that work is done. Evidence does.

## Choose the right amount of proof

Use the cheapest proof that directly verifies the requested outcome.

- `light`: default for small tasks; at most 4 checks per gate.
- `standard`: feature boundaries or meaningful integration; at most 7 checks.
- `strict`: auth, permissions, money, migrations, destructive operations, or other high-risk work; at most 12 checks.

Do not choose a heavier mode just because it sounds safer.

## Before implementation

For non-trivial work, create `.proof-of-done/contract.json` and lock it before
changing implementation files.

Use 2–4 checks for a normal task. Prove:

1. the requested behavior or output works;
2. changed persistent or external state can be read back and compared;
3. the smallest relevant regression check still passes.

Prefer behavior, API/database state, tests, and runtime evidence over source
inspection or file existence.

Lock the contract:

    python3 <skill-dir>/scripts/pod.py lock .proof-of-done/contract.json

Do not weaken a locked contract because implementation failed.

## Loop protocol

    implement -> verify task gate -> PASS: continue
                                 -> FAIL: repair -> verify again

Verify the gate for the current task. A selected feature or milestone gate also
rechecks its declared dependencies; use those gates only when closing that
boundary, not on every task.

After three reasonable repair attempts on the same gate without new evidence,
stop thrashing and report the real failure or blocker.

## Verification rules

- A successful write or tool call is not proof of final state.
- Another agent's summary and reasoning are not proof.
- Mutations require: write -> read back -> compare.
- Bug fixes should reproduce the original failure when practical.
- Use the concise CLI result; inspect the ledger only when debugging.
- Never advance on `FAILED`, `BLOCKED`, or `VERIFIED_PARTIAL`.

Verify a gate:

    python3 <skill-dir>/scripts/pod.py verify .proof-of-done/contract.json --gate <gate-id>

The verifier stops at the first failed check and writes detailed evidence to
`.proof-of-done/ledger.json`.

## Completion

Only `VERIFIED_SUCCESS` permits a completion claim. Otherwise report the real
status and the smallest useful failure summary.
