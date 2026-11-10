---
name: doneproof
description: Protect acceptance criteria, automatically verify regressions in affected flows proportionally to change risk, and verify completion for coding changes and execution of implementation plans. Skip questions, read-only analysis, planning without execution and trivial prose edits unless explicitly requested.
---

# DoneProof

Before editing, read the request and source; record every requested outcome and relevant existing behavior to preserve as observable criteria in acceptance files. Automatically select and run regression checks for affected flows, without waiting for a separate user request. For behavioral work, completion requires `VERIFIED_SUCCESS` and a brief comparison of the original request with current evidence. Close missing evidence or report the gap. Follow the user's scope and existing authorization; do not introduce repeated approval questions.

## Validate a delivery, not each edit

Use one contract for a coherent user request, affected module or independently deliverable stage. Include its related files and flows in that contract. Do not create a contract per line, function or intermediate edit. During implementation, use focused checks when they help diagnose or develop; run the final graph when the delivery is ready, or validate a gate at a meaningful milestone. Never run the full suite repeatedly as a ritual.

Keep current local evidence when its declared inputs, criteria, runtime and dependencies still match. `finish --reuse` validates those identities and reruns stale or missing gates; HTTP observations and readback checks always rerun. Default `finish` obtains fresh evidence; use it for commands observing mutable external state that is not represented by declared inputs. After relevant changes, reverify the affected gates and their dependents; do not reuse an old success merely because its output was green. Tiny edits with no behavioral impact need review appropriate to their scope, without artificial tests or a new contract.

## Choose proportionate verification

| Work | Mode | Affected-flow regression scope |
| --- | --- | --- |
| Small local change | `light` | Focused checks of changed behavior and existing behavior at risk in the local flow and direct callers. |
| Feature crossing an integration boundary | `standard` | Relevant component suites plus checks across the affected boundary, including consumers and failure paths at risk. |
| Authentication, permissions, money, migrations or destructive operations | `strict` | All identified affected critical flows, with success, rejection/failure and persisted-state checks where applicable. |

Choose risk by behavior, not patch size: a one-line permission change is strict. Long plans additionally use `kind: plan`. For integrations, strict work, artifacts or plans, read [the extended workflow](references/workflow.md). The shortcut below creates only a light task.

## Select regressions before editing

Trace the intended change through callers, shared components, contracts, data and relevant configuration; inspect existing tests. Record a concise impact map in protected acceptance files: affected flow → behavior to preserve → selected test/assertion and command. Use the request and intended contract as the oracle; a baseline does not make an existing bug correct. A diff alone cannot establish impact.

Reuse project tests first. Add or extend durable project regression tests only for meaningful uncovered behavior at risk; keep editable tests separate from protected acceptance, which records the expected outcomes and test selection. For a bug, retain a focused regression test, reusing one if it already reproduces the failure. Trivial edits with no behavioral impact need no artificial tests; record why that scope applies.

When feasible, run selected existing checks before editing to establish a baseline, and reproduce the reported bug. Record pre-existing failures and reproduction limits. Include selected regressions in final verification, within final's dependency graph; the light command can run acceptance and regressions together. A build, zero selected tests or skipped relevant assertions is not regression evidence. For supported test commands, use counted verification and protect required case IDs; `init` recognizes Python `-m unittest` and `bun test` automatically. For other runners or custom acceptance scripts, assert execution and outcomes explicitly. See [evidence and controls](references/evidence.md) for counted runners, obligation mapping and evidence classes.

Expand the selection when shared code, dependency/configuration changes or new failures reveal more affected flows. Run the full suite when impact is broad or cannot be bounded with evidence, not for every local edit. Extend protected coverage before implementing newly discovered scope; use the extended workflow when needed. Unavailable required checks or unresolved failures in selected flows remain explicit evidence gaps; do not claim full completion. Identify unrelated baseline failures without expanding the repair scope. In the final comparison, briefly identify flows checked and any limits, reusing recorded results.

## One small delivery

Reuse project tests or prepare acceptance assertions for the requested outcomes and selected regressions. For behavior changes, exercise the affected UI/API/CLI flow; a build alone is insufficient. Keep editable product/tests separate from protected acceptance. Include relevant source, regression tests, fixtures and configuration as inputs; directories cover new files. Git is optional.

From the project root, protect the criteria before changing product code:

```sh
python3 <skill-dir>/scripts/pod.py init .proof-of-done/<task-id>/contract.json --input app.py --criterion acceptance.py --run python3 acceptance.py
```

Use project paths and commands. Repeat `--input` and `--criterion` as needed. Criteria files must exist; `--run` goes last, with separate argument tokens. Put standalone Python acceptance scripts where root-module imports resolve, or use the project's test runner.

Edit with native tools, then conclude:

```sh
python3 <skill-dir>/scripts/pod.py finish .proof-of-done/<task-id>/contract.json
```

`finish` runs final and its dependencies, stops on failure, and finalizes a passing task. If meaningful milestones already produced current local evidence, use `finish <contract> --reuse` to avoid repeating it. Confirm the intended acceptance and regression tests ran and demonstrate each requested outcome and preserved behavior; a PASS only covers declared criteria. Reuse that evidence for the request comparison, without a separate checklist, coverage call or duplicate verification. Successful small tasks need no schema reading or verifier inspection. The [code example](examples/code/.proof-of-done/contract.json) includes separate acceptance and regression checks in a light final gate.

## Recover and resume

Use reported evidence to investigate failures in product behavior, test selection or execution environment before repairing. Never weaken locked criteria to obtain PASS. For a confirmed light-task criterion error, preserve the original file/history, write a corrected file, and run `init` in a new task directory with `--supersedes <old-contract> --reason '<specific correction>'` before `--run`. New proof remains mandatory. Other replacements and authorized additions use the extended workflow.

Use `coverage <contract> --summary` when resuming or diagnosing an existing task. Stop repeated repairs when they produce no new evidence and report the remaining blocker. Changes or new attempts invalidate relevant old proofs. Match the scope of repair and revalidation to the affected gates.

Use a separate state directory per task. Checks must observe or operate in isolated fixtures; never replay production writes for verification. If activated after implementation began, disclose that criteria lacked prior protection. Meaningful tests, complete inventories and semantic review remain the agent's responsibility. See [recovery and platform boundaries](README.md) when needed.
