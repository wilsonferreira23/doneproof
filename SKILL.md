---
name: doneproof
description: Protect acceptance criteria and verify completion for coding changes and execution of implementation plans. Skip questions, read-only analysis, planning without execution and trivial prose edits unless explicitly requested.
---

# DoneProof

Before editing, read the request and source; record every requested outcome as an observable criterion in existing acceptance files. Completion requires `VERIFIED_SUCCESS` and a brief comparison of the original request with current evidence, even for small tasks. Close missing evidence or report the gap. Follow the user's scope and existing authorization; do not introduce repeated approval questions.

## Choose proportionate verification

| Work | Mode |
| --- | --- |
| Small local change | `light` |
| Feature crossing an integration boundary | `standard` |
| Authentication, permissions, money, migrations or destructive operations | `strict` |

Choose risk by behavior, not patch size: a one-line permission change is strict. Long plans additionally use `kind: plan`. For integrations, strict work, artifacts or plans, read [the extended workflow](references/workflow.md). The shortcut below creates only a light task.

## Small changes

Reuse project tests or prepare acceptance assertions for those criteria. For bugs, reproduce the failure before editing when feasible and rerun the check afterward; disclose reproduction limits. For behavior changes, exercise the affected UI/API/CLI flow; a build alone is insufficient. Keep editable product/tests separate from protected acceptance. Include relevant source, fixtures and configuration as inputs; directories cover new files. Git is optional.

From the project root, protect the criteria before changing product code:

```sh
python3 <skill-dir>/scripts/pod.py init .proof-of-done/<task-id>/contract.json --input app.py --criterion acceptance.py --run python3 acceptance.py
```

Use project paths and commands. Repeat `--input` and `--criterion` as needed. Criteria files must exist; `--run` goes last, with separate argument tokens. Put standalone Python acceptance scripts where root-module imports resolve, or use the project's test runner.

Edit with native tools, then conclude:

```sh
python3 <skill-dir>/scripts/pod.py finish .proof-of-done/<task-id>/contract.json
```

`finish` runs final and its dependencies, stops on failure, and finalizes a passing task. Confirm the intended tests ran and demonstrate each requested outcome; a PASS only covers declared criteria. Reuse that evidence for the request comparison, without a separate checklist, coverage call or duplicate verification. Successful small tasks need no schema reading or verifier inspection.

## Recover and resume

Use reported evidence to investigate failures in product behavior, test selection or execution environment before repairing. Never weaken locked criteria to obtain PASS. For a confirmed light-task criterion error, preserve the original file/history, write a corrected file, and run `init` in a new task directory with `--supersedes <old-contract> --reason '<specific correction>'` before `--run`. New proof remains mandatory. Other replacements and authorized additions use the extended workflow.

Use `coverage <contract> --summary` when resuming or diagnosing an existing task. Stop repeated repairs when they produce no new evidence and report the remaining blocker. Changes or new attempts invalidate relevant old proofs.

Use a separate state directory per task. Checks must observe or operate in isolated fixtures; never replay production writes for verification. If activated after implementation began, disclose that criteria lacked prior protection. Meaningful tests, complete inventories and semantic review remain the agent's responsibility. See [recovery and platform boundaries](README.md) when needed.
