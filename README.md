# DoneProof

DoneProof checks declared acceptance evidence before a coding agent claims
completion. The CLI stays in Python's standard library. It does not measure the
semantic truth of arbitrary tests or the completeness of a natural-language plan.

Read [SKILL.md](SKILL.md) for the agent workflow and
[references/contract.md](references/contract.md) for the schema and audit format.

From the skill directory, run:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_package.py
```

The runnable examples live in `examples/basic`, `examples/code` and `examples/strict`. Copy an
example to a temporary project before executing it so the distributed examples
remain clean. The package check does this automatically.

Only `finalize` emits global `VERIFIED_SUCCESS`. `GATE_PASS` and
`COVERAGE_COMPLETE` are intermediate results. Every new verification attempt
invalidates old dependent evidence. Product inputs and protected criterion files
are fingerprinted; completed proofs retain detailed observations and dependency
references. State updates are atomic and operations are serialized per task.

## Migration from 2.2

This is schema 3, not a transparent state upgrade. Preserve 2.2 contract, plan,
ledger and history as historical records. Create a new contract in a new task
directory and execute fresh proofs. Never copy PASS records into schema 3.
Update scripts that interpreted any `verify` success as overall completion.

The state directory is now the contract directory, independent of the process
working directory. Use `.proof-of-done/<task-id>/contract.json` with `root: ../..`.
For a justified replacement of criteria, create a new task directory and record
`supersedes` with old task ID, contract digest and reason; preserve the old data.
Authorized additions to the original plan use immutable `plan_additions` files.

## Recovery and boundaries

A killed process can leave RUNNING state. Reexecute its gate, then affected
integrations. OS advisory locks are released when the process exits; do not delete
a live lock file to start a competing verifier. A corrupted state/proof blocks
completion. Recover from a known-good backup or create a new task and rerun proof;
never relabel damaged evidence as PASS.

Input inventories must include relevant source, fixtures and configuration.
Hashes detect changes to declared files, not undisclosed dependencies. Commands
must be observational or isolated; declarations alone cannot infer effects.
HTTP observations prove external state at the recorded time. Permanent services
and production writes do not belong inside a verification command.

Supported target platforms are Linux and macOS with Python 3.10+. The CI workflow
covers both. Windows, symlinks, special-file inputs and distributed shared-state
execution are not supported. See the contract reference for bounded input/output
sizes, credential handling and check constraints.

The independent agent benchmark is described in `references/evaluation.md`.
An installed candidate is not a demonstrated 9/10 release: empirical results,
false-block rate, completion rate and token costs must meet the frozen protocol.
The historical research links in the 2.2 audit motivate the approach; they are
not benchmark results for this implementation.

This package has no license grant. Preserve the existing ownership/licensing
status when redistributing it.

See [historical rc1 validation](references/validation.md). The reserved final evaluation is reported separately; historical pilot results
do not qualify this release by themselves.

Small code tasks can use `pod.py init` to generate and lock a light contract from existing acceptance files. See SKILL.md for the complete command; full contracts remain available for plans and higher-risk work.
