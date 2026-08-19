---
name: doneproof
description: Deterministic completion and plan-coverage gate for coding agents and looping engineering. Use before claiming implementation work is done, especially for long plans. Requires locked criteria, targeted verification, repair on failure, and 100% mapped plan coverage before final success.
---

# DoneProof 2.2

Evidence decides when work is done.

## Modes

Choose automatically:
- `strict`: auth, permissions, money, migrations, destructive/high-risk work; max 12 checks/gate.
- `standard`: feature/integration boundary; max 7.
- `light`: everything else; max 4.

Normal tasks should still use only 2-4 useful checks.

## Before implementation

For non-trivial work, create `.proof-of-done/contract.json` and lock it.

For a large plan or multi-feature loop:
1. save the original user plan unchanged to `.proof-of-done/plan.md`;
2. add `plan_path`, `requirements`, and `final_gate` to the contract;
3. give each required outcome a stable ID (`R1`, `R2`, ...);
4. map every requirement to the gate that proves it.

Keep requirement text short. The matrix is for coverage, not documentation.

Lock:

    python3 <skill-dir>/scripts/pod.py lock .proof-of-done/contract.json

Do not weaken locked criteria after failure.

If the final audit discovers a requirement that was genuinely omitted from the contract, only ADD it (and any new gate) then run:

    python3 <skill-dir>/scripts/pod.py extend .proof-of-done/contract.json

`extend` rejects edits/removals of existing requirements or gates.

## Loop

    implement -> targeted task gate -> FAIL: repair -> same gate
                                    -> PASS: next task

Verify:

    python3 <skill-dir>/scripts/pod.py verify .proof-of-done/contract.json --gate <gate-id>

Use feature gates only when a feature closes and milestone gates at real checkpoints.
After 3 reasonable repairs on the same gate without materially new evidence, stop thrashing and report the blocker.

## Verification rules

- Tool success, agent reasoning, and another agent's summary are not proof.
- Mutations require write -> read back -> compare.
- Prefer observable behavior/state over source inspection.
- Never advance on `FAILED`, `BLOCKED`, or `VERIFIED_PARTIAL`.
- Use concise CLI output; inspect ledger only to debug.

## Plan Coverage Loop

For large plans, after implementation:

1. run the final integration/module gate;
2. run deterministic coverage:

       python3 <skill-dir>/scripts/pod.py coverage .proof-of-done/contract.json

3. read `.proof-of-done/plan.md` and `.proof-of-done/coverage.json` once;
4. assume something may be missing and compare the original plan against:
   - requirement IDs,
   - implemented behavior,
   - verification evidence;
5. if something is missing/partial: add the omitted requirement/gate with `extend`, implement it, verify it, rerun the final gate, then rerun coverage;
6. stop only when no semantic gap is found and coverage returns `VERIFIED_SUCCESS coverage=100%`.

Do not repeat the semantic audit when nothing new changed.

## Completion

For normal tasks, the applicable gate must return `VERIFIED_SUCCESS`.

For a large plan, BOTH are required:
- final gate: `VERIFIED_SUCCESS`;
- coverage: `VERIFIED_SUCCESS coverage=100%`.

100% coverage means every explicitly extracted requirement has executable proof. It is strong evidence, not mathematical certainty.
