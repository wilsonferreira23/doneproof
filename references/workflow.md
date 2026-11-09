# DoneProof extended workflow

## Prepare

Apply the acceptance, evidence and risk guidance in [SKILL.md](../SKILL.md). Create a contract in
`.proof-of-done/<task-id>/contract.json`, with `root: ../..`. Adapt the
[standard template](contract.md#standard-template), [artifact example](../examples/basic/.proof-of-done/contract.json)
or [strict plan example](../examples/strict/.proof-of-done/contract.json).
Read the [schema](contract.md) only for fields the chosen example does not cover.

Declare relevant source, test fixtures and configuration as inputs. Protected
criteria express the agreed acceptance; ordinary tests that need implementation
can remain editable product inputs, with a separate protected acceptance file.
Git diffs help inspect changes but do not enumerate every dependency. Checks must
not write into their input inventory; use temporary fixtures outside it.

Apply the affected-flow impact map from SKILL.md before locking. Put selected
regression commands in final or its dependency gates, alongside acceptance;
include their source, tests, fixtures and configuration in the input inventory.
Use existing schema purposes: regression checks usually have `purpose: behavior`,
or `integration`, `negative` or `readback` when those assertions actually apply.
There is no `regression` purpose. One command may cover acceptance and regressions
if its real assertions cover both; purpose labels alone do not establish coverage.

For standard work, exercise the affected caller/provider or component interaction
and existing consumer contracts. For strict work, also cover applicable permission
boundaries, invalid states and data invariants, and retry/idempotency or recovery
behavior when the change can affect them. Prefer isolated integration tests;
use end-to-end checks when lower-level tests cannot prove the affected flow.
Broaden suites based on actual impact, not an arbitrary test count.

For a plan, preserve the original unchanged, set `kind: plan`, and map every
required outcome to its literal source excerpt and a proof gate. Administrative
steps do not need artificial tests. Preserve authorized additions in separate
`plan_additions` files. Choose the mode by risk, independently of plan length.
Record regression safety criteria separately from literal plan excerpts; do not
invent user requirements or rewrite the preserved plan to justify test coverage.

Lock before editing:

```sh
python3 <skill-dir>/scripts/pod.py lock <contract>
```

The initial lock checks command executables and working directories without
executing tests. Then edit with native tools. Verify at meaningful milestones
using `verify <contract> --gate <id>`. Final verification reruns its dependencies;
avoid separately running those gates immediately before final merely as ritual.
Requirements outside final's dependency graph must be verified before final.

Standard work requires a behavior check and final integration. Strict also
requires a meaningful negative control: demonstrate rejection of a known wrong
state in an isolated fixture. Purpose labels do not establish meaningful tests.
For mutations, map each persisted outcome to a `readback` check that independently
reads and compares the saved state. Never replay production writes for evidence.

## Finish and audit

```sh
python3 <skill-dir>/scripts/pod.py finish <contract>
```

Tasks finalize after passing verification. Plans return `AUDIT_REQUIRED` (exit 2)
and the path to `audit-draft-<snapshot>.json`, with identity fields filled and
assessments blank. This expected pending state is not a test failure or approval.

Compare the original request, preserved plan and additions with implemented behavior, requirements
and referenced proofs, including affected-flow regression results and unresolved
baseline or environment limits. Fill every `assessment`, the whole `plan_review`, and
`gaps` honestly. Coverage only proves the explicitly declared mapping. The CLI
cannot determine whether a reviewer's prose is true. Finalize that snapshot:

```sh
python3 <skill-dir>/scripts/pod.py finish <contract> --audit <draft-path>
```

This call never reruns tests. Stale evidence/audits block. After repairing gaps,
run `finish` without `--audit` for fresh proofs and a new draft; preserve the old
review. For manually verified current evidence, `finalize --audit` remains valid.
Only current `VERIFIED_SUCCESS` authorizes a full completion claim.

## Extend, recover and coordinate

Authorized additions use `extend`: add gates/requirements to the contract, then
run `extend <contract>`. Existing gates, criteria and outcomes cannot be weakened
or removed. A justified replacement uses a new task directory and `supersedes`
with the previous task ID, contract digest and specific reason; preserve the old
files and obtain new evidence. Do not downgrade risk to escape required checks.
The light-task shortcut is documented in SKILL.md.

`coverage <contract> --summary` reports the project root, revision, requirement
states, stale reasons and evidence path. Resume from those records rather than
conversation memory. For interrupted checks, rerun their gate and affected final
integration. For damaged state, preserve history and restore a known-good backup
or create a fresh task. Never delete locks/history to turn failure into PASS.

Use one coordinator for the overall contract and explicit scopes for subagents.
Separate tasks need separate state directories. Prefer worktrees for overlapping
edits. OS locks serialize verifier operations per task; they do not lock editors
or other contracts. Relevant concurrent changes invalidate evidence. Agent
summaries alone are not proof. See [installation and recovery](../README.md) for
updates, rollback and platform limitations.
