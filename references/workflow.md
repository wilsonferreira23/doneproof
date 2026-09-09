# DoneProof 3

Only `finalize` authorizes a completion claim. Gate PASS and complete coverage are intermediate results.

## Prepare before implementation

For a small code change, adapt the [code example](../examples/code/.proof-of-done/contract.json); for an artifact use the [file example](../examples/basic/.proof-of-done/contract.json). Read [the contract reference](contract.md) for additional fields, plans or audits, and use the [strict plan example](../examples/strict/.proof-of-done/contract.json) when applicable. Commands below use the installed skill's `scripts/pod.py`.

For nontrivial work, create `.proof-of-done/<task-id>/contract.json`, with `root` relative to that directory. Use a separate directory for each task. Declare the product inputs, protected acceptance files, checks, and final gate. Product inputs may change during implementation; protected criteria may not silently change after locking. Include relevant test fixtures/configuration and newly created source directories in the inventory.

Choose `light` for a small outcome, `standard` for a feature/integration boundary, and `strict` for auth, permissions, money, migrations or destructive work. Limits are 4/7/12 checks per gate. Normally 2–4 useful checks suffice. Standard requires behavior and final integration proof; strict also requires a relevant negative/control case. Categories describe checks; they do not prove that a test is meaningful.

For a large plan, choose `kind: plan`, preserve the user's original plan unchanged, and map every required outcome to a stable requirement ID, a literal source excerpt and a proof gate. Preserve authorized additions separately with `plan_additions`.

Lock before implementation:

    python3 <skill-dir>/scripts/pod.py lock <contract>

Use existing project tests. Check that the test runner selected real tests. For critical behavior, demonstrate that the acceptance test rejects a known wrong state in an isolated fixture. Do not treat a process exiting zero, a source substring or another agent's summary as sufficient proof of behavior.

## Implement and verify

Implement → verify the closing task gate → repair on failure → verify that gate again.

Batch tool calls when their dependencies allow. Lock, implementation and verification may share a scripted call if lock runs first and every failure stops the script. Keep successful check output concise.

    python3 <skill-dir>/scripts/pod.py verify <contract> --gate <gate-id>

Never advance on failure, blockage, interruption or stale evidence. A new attempt invalidates old dependent proofs. Run feature/final gates at actual checkpoints; dependency gates execute again. Inspect the referenced proof when diagnosing a failure. After three reasonable repairs without materially new evidence, report the blocker; the CLI cannot judge whether new evidence is meaningful.

Keep verification observational or isolated. Mutations require write → independent read-back → comparison with the intended persisted state. Map each mutation to a `readback` check. A successful write response alone is insufficient. Never replay a production write merely to refresh proof; arbitrary commands require effect review. HTTP checks are GET/HEAD only.

Do not weaken locked tests to make failures pass. Add omitted outcomes/gates with `extend`; it preserves existing criteria and invalidates the affected proofs and final. A legitimate replacement of criteria needs a new task contract with `supersedes` and a recorded reason, preserving the original. Use existing user authorization; this does not require repetitive approval questions.

    python3 <skill-dir>/scripts/pod.py extend <contract>

## Complete

Execute the final gate, then `coverage`. Coverage means valid evidence exists for the explicitly extracted outcomes, not that every intended outcome was extracted.

    python3 <skill-dir>/scripts/pod.py coverage <contract>

For a plan, compare the preserved plan and additions against requirement IDs, implemented behavior and the referenced proof files. Assume something may be missing. Record each assessment and the whole-plan review in the [audit format](contract.md#audit). Do not generate an automatic positive assessment from coverage alone. Fix gaps using the extension loop, rerun affected gates and final, then redo the changed audit. No repeated semantic audit is needed when the relevant snapshot is unchanged.

    python3 <skill-dir>/scripts/pod.py finalize <contract> --audit <audit.json>

For `kind: task`, omit `--audit`. Only a current `VERIFIED_SUCCESS` from this command permits claiming completion. Inputs or proofs changing afterward require revalidation; a saved completion report is not permanent authorization. External state is proved at the recorded observation time.

If work began without a contract, verify the current result and disclose that the criteria were not locked beforehand. Never claim retroactive protection. For 2.2 state migration, recovery and platform limits, read [README.md](../README.md).

The CLI detects stale, incomplete or contradictory declared evidence. The agent remains responsible for complete input inventories, meaningful tests and semantic review. Local hashes do not protect against a hostile process rewriting the verifier and its entire state.
