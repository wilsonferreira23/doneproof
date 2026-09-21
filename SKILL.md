---
name: doneproof
description: Protect acceptance criteria and verify completion for coding changes and execution of implementation plans. Skip questions, read-only analysis, planning without execution and trivial prose edits unless explicitly requested.
---

# DoneProof

Define what must work before editing, then obtain current evidence. Completion requires `VERIFIED_SUCCESS` from finalization, directly or through `finish`. Failed verification still permits an honest progress or blocker report. Follow the user's scope and existing authorization; do not introduce repeated approval questions.

## Choose proportionate verification

| Work | Mode |
| --- | --- |
| Small local change | `light` |
| Feature crossing an integration boundary | `standard` |
| Authentication, permissions, money, migrations or destructive operations | `strict` |

Patch size does not determine risk. A one-line permission change is strict. Executing a long plan additionally uses `kind: plan`; choose its mode by risk. For integrations, strict work, artifacts or plans, read [the extended workflow](references/workflow.md). The shortcut below creates only a light task.

## Small changes

Read the request and relevant source. Reuse meaningful project tests or prepare acceptance assertions for the requested outcome. Distinguish editable product/tests from protected acceptance criteria; use a separate acceptance file when project tests must change. Include relevant source, fixtures and configuration in the input inventory. Directories cover newly created files. Git is optional.

From the project root, protect the criteria before changing product code:

```sh
python3 <skill-dir>/scripts/pod.py init .proof-of-done/<task-id>/contract.json --input app.py --criterion acceptance.py --run python3 acceptance.py
```

Replace the example paths and command with the project's actual acceptance check. Repeat `--input` and `--criterion` as necessary. Acceptance files must already exist. `--run` goes last and receives separate argument tokens, not one quoted command string. Put standalone Python acceptance scripts where root-module imports resolve; otherwise use the project's existing test runner.

Edit with native tools, then conclude:

```sh
python3 <skill-dir>/scripts/pod.py finish .proof-of-done/<task-id>/contract.json
```

`finish` runs the final gate and its dependencies, stops on failure, and finalizes a passing task. Confirm the intended tests actually ran and assertions demonstrate the requested behavior. Successful small tasks need no separate coverage call, duplicate verification, schema reading or inspection of verifier internals. No staging folder or full-file rewrite is required.

## Recover and resume

On failure, use the reported evidence and next action. Investigate product behavior, test selection and execution environment before deciding what to repair. Never weaken locked criteria to obtain PASS. For a confirmed light-task criterion error, preserve the original file/history, write a corrected file, and run `init` in a new task directory with `--supersedes <old-contract> --reason '<specific correction>'` before `--run`. New proof remains mandatory. Other replacements and authorized additions use the extended workflow.

Use `coverage <contract> --summary` when resuming or diagnosing an existing task. Stop repeated repairs when they produce no new evidence and report the remaining blocker. Changes or new attempts invalidate relevant old proofs.

Use a separate state directory per task. Checks must observe or operate in isolated fixtures; never replay production writes for verification. If activated after implementation began, disclose that criteria lacked prior protection. Meaningful tests, complete inventories and semantic review remain the agent's responsibility. See [recovery and platform boundaries](README.md) when needed.
