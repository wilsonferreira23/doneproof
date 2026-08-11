---
name: doneproof
description: Mandatory loop-aware completion gate for coding tasks. Use before claiming a task, feature, milestone, bug fix, migration, integration, refactor, or implementation is complete. Requires a locked success contract, deterministic evidence, task/feature/milestone gates, read-after-write verification, and repair on failure.
---

# DoneProof

Completion is a state proved by evidence, not a conclusion produced by an agent.

## Non-negotiable rule

Never claim:

- done
- fixed
- implemented successfully
- working
- complete
- ready

unless the applicable gate returns `VERIFIED_SUCCESS`.

Agent reasoning is not evidence.

Another agent's report is not evidence.

A successful write/tool call is not evidence of final state.

---

# Workflow

For non-trivial implementation work:

1. Understand the requested outcome.
2. Inspect the affected code and existing verification.
3. Create `.proof-of-done/contract.json`.
4. Lock the contract BEFORE implementation.
5. Implement the smallest correct change.
6. Run the applicable Task Gate.
7. Repair failures.
8. Repeat until the Task Gate passes.
9. Run Feature Gate when the feature is complete.
10. Run Milestone Gate before advancing to another milestone.
11. Only report success when the applicable gate returns VERIFIED_SUCCESS.

---

# Success Contract

Translate the user's requested outcome into observable conditions.

Every condition must describe something that can actually be checked.

Bad:

- authentication implemented
- endpoint added
- looks correct

Good:

- unauthenticated request to /dashboard returns redirect to /login
- authenticated request can access /dashboard
- persisted record can be read back with the expected value
- regression test passes
- production build succeeds

Create the contract before changing implementation files.

Then lock it using the bundled verifier:

    python3 <skill-path>/scripts/pod.py lock .proof-of-done/contract.json

After implementation begins, do not replace or weaken the contract merely because verification fails.

If the USER changes requirements, the contract may be replaced and re-locked intentionally.

---

# Gates

There are three gate levels.

## Task Gate

Runs after each bounded implementation task.

Examples:

- endpoint implemented
- validation fixed
- component changed
- migration added

A loop may not mark the task complete until its Task Gate passes.

## Feature Gate

Runs after all tasks belonging to a user-visible feature pass.

Feature verification must exercise integration between components.

Prefer:

UI
→ API
→ business logic
→ persistence
→ read-back
→ UI/API observable result

Individual task success does not imply feature success.

## Milestone Gate

Runs before moving the engineering loop to another major area.

Run the smallest relevant:

- smoke tests
- integration tests
- E2E tests
- build
- typecheck
- regression suite

Do not run unrelated expensive verification without reason.

---

# No Transitive Trust

Never accept another agent's completion claim as proof.

Forbidden:

Builder:
"Tests passed."

Orchestrator:
"Builder says tests passed, therefore continue."

Required:

Builder
→ changes implementation

Verifier
→ executes checks independently

Evidence
→ VERIFIED_SUCCESS

Orchestrator
→ advances loop

Subagent summaries may explain work but cannot satisfy a gate.

---

# Mutation Rule

Persistent or external state changes require read-after-write verification.

WRITE
→ READ BACK
→ COMPARE

Examples:

database:

    INSERT/UPDATE
    → SELECT
    → compare expected state

API:

    POST/PATCH/DELETE
    → GET/query state
    → compare expected state

filesystem:

    WRITE
    → READ
    → compare expected contents

deployment:

    DEPLOY
    → query deployed application
    → exercise expected behavior

Do not trust acknowledgement of a mutation as proof of its result.

---

# Bug Fix Rule

Reproduce the original failure whenever possible.

The preferred sequence is:

REPRODUCE FAILURE
→ IMPLEMENT FIX
→ RE-RUN REPRODUCTION
→ RUN RELEVANT REGRESSION CHECKS

A bug is not VERIFIED_SUCCESS merely because the changed code looks correct.

---

# Repair Loop

When a gate fails:

1. Keep the failure evidence.
2. Find the root cause.
3. Change the implementation.
4. Do not weaken the contract.
5. Re-run the failed gate.
6. Re-run affected checks.

Continue while useful progress is possible.

Do not advance to the next loop item after FAIL, BLOCKED, or VERIFIED_PARTIAL.

---

# Contract Integrity

The verifier stores a SHA-256 digest when the contract is locked.

Verification must stop if the contract differs from the locked version.

This prevents accidental success-criteria drift during repair loops.

Never delete or replace the lock because implementation failed.

A changed user requirement is a legitimate reason to create a new contract.

---

# Verification Evidence

Prefer evidence in this order:

1. observed final system state
2. deterministic E2E verification
3. integration test
4. runtime/API/database read-back
5. unit test
6. typecheck/build/static analysis
7. source inspection
8. tool acknowledgement
9. agent reasoning

Use the strongest practical evidence.

Reasoning alone can never produce VERIFIED_SUCCESS.

---

# Loop Protocol

For looping engineering:

    PLAN
      ↓
    TASK
      ↓
    IMPLEMENT
      ↓
    TASK GATE
      ↓
    FAIL ──→ REPAIR ──┐
      ↑               │
      └───────────────┘
      ↓ PASS
    NEXT TASK
      ↓
    FEATURE GATE
      ↓
    FAIL → REPAIR
      ↓ PASS
    CHECKPOINT
      ↓
    NEXT FEATURE
      ↓
    MILESTONE GATE
      ↓
    NEXT MILESTONE

The orchestrator must not advance through a failed gate.

---

# Final Status

The verifier owns the completion state.

Possible states:

## VERIFIED_SUCCESS

All required checks for the requested gate passed.

The agent may report completion.

## VERIFIED_PARTIAL

Some evidence passed, but the requested gate did not.

Do not report completion.

## BLOCKED

Verification could not execute due to an external constraint.

Examples:

- unavailable credentials
- unavailable service
- missing required runtime
- inaccessible environment

Do not report completion.

## FAILED

Required observed behavior differs from expected behavior.

Do not report completion.

---

# Final Response

Only after VERIFIED_SUCCESS:

    VERIFIED_SUCCESS

    Implemented:
    - <small summary>

    Verified:
    - <important observable evidence>

    Checks:
    - <relevant checks>

Otherwise clearly report the actual verifier status.

Never convert uncertainty into success.
