---
name: doneproof
description: Define acceptance criteria before coding work and verify completion using current evidence. Use for implementation and long plans; protects criteria, tracks product changes and dependencies, and gates the final completion claim.
---

# DoneProof 3

Only `finalize` emitting `VERIFIED_SUCCESS` authorizes completion. Gate PASS and coverage are intermediate results.

## Choose the workflow first

For integration, critical changes or long plans, read [the extended workflow](references/workflow.md) and [contract reference](references/contract.md). Use `standard` for integration boundaries; `strict` for auth, permissions, money, migrations or destructive work, with meaningful negative controls. Verify mutations through independent persisted-state readback, in isolation. See the [strict example](examples/strict/.proof-of-done/contract.json).

For long plans, preserve the original, map every outcome to its source and proof, execute final integration, then audit semantic coverage before `finalize --audit`. Mechanical mapping alone cannot establish completeness.

The `init` shortcut below creates only a `light` task. Use it only for small changes that do not involve an integration boundary, critical operation or long plan. Integration requires `standard` even when the patch is small.

## Small changes

For this light code workflow, read the request and relevant source, then execute directly. Do not read verifier internals, schemas, examples or CLI help unless the documented workflow fails. Git inspection is unnecessary when the project has no Git repository.

For a small full-file change, use ONE fail-fast shell call to write meaningful acceptance tests, stage the source, lock, copy, verify and finalize. Put a standalone Python acceptance script in the project root so imports of root modules work; use the project's existing test runner for an established test suite. Preparing a staged file does not change product code; copying it into place must follow the lock:

```sh
set -e
# From the project root; replace both bodies with actual code:
mkdir -p .proof-of-done/<task-id>/staged
cat > acceptance.py <<'TEST'
# meaningful assertions for the requested behavior
TEST
cat > .proof-of-done/<task-id>/staged/app.py <<'SOURCE'
# finished source
SOURCE
python3 <skill-dir>/scripts/pod.py init .proof-of-done/<task-id>/contract.json --input app.py --criterion acceptance.py --run python3 acceptance.py
cp .proof-of-done/<task-id>/staged/app.py app.py
python3 <skill-dir>/scripts/pod.py verify .proof-of-done/<task-id>/contract.json --gate final
python3 <skill-dir>/scripts/pod.py finalize .proof-of-done/<task-id>/contract.json
```

Use actual source/test paths without overwriting unrelated files. Repeat `--input` and `--criterion` for relevant files or source directories. `--run` goes last and takes separate argument tokens, never one quoted command string. `init` rejects unavailable executables before locking; it never executes or weakens tests. When a full-file rewrite is unsuitable, use native editing tools with the same lock-before-edit order, then batch verification and finalization. For artifact checks use the [file example](examples/basic/.proof-of-done/contract.json).

Batch initial project inspection with reading this skill. The verifier fingerprints files directly; Git is optional. Lock before changing product code. Batch verification and finalization, stopping on errors. Confirm the verification actually ran the intended tests. Inspect detailed proof to diagnose failures; successful small tasks need no extra state inspection, coverage call or duplicate verification.

Never weaken locked criteria. Authorized additions use `extend`. For an independently confirmed error in a light task's acceptance criterion, preserve the old file and history, write the corrected criterion to a new file, and initialize a new task using the same command plus `--supersedes <old-contract> --reason '<specific correction>'` before `--run`. This records the replacement without manual contract editing; it still requires new verification and finalization. Other justified replacements use the full workflow. Changed inputs or new attempts invalidate relevant old proofs. After three repairs without new evidence, report the blocker.

If started late, disclose that criteria lacked prior protection. Meaningful tests and complete inventories remain the agent's responsibility. Local hashes do not defend against a hostile verifier rewrite. See [migration and recovery](README.md).
