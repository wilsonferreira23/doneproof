<div align="center">

# DoneProof

### Give every “done” a proof you can inspect.

Acceptance criteria, affected-flow regressions, and verified completion for AI-assisted development.

[![Checks](https://github.com/wilsonferreira23/doneproof/actions/workflows/tests.yml/badge.svg)](https://github.com/wilsonferreira23/doneproof/actions/workflows/tests.yml)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Platforms](https://img.shields.io/badge/Platforms-Linux%20%7C%20macOS-222222)
![Runtime dependencies](https://img.shields.io/badge/Runtime-Python%20standard%20library-0F766E)

[Get started](#get-started) · [See it in action](#a-fix-can-work-and-still-break-something) · [Read the workflow](SKILL.md)

</div>

---

You ask an agent to fix a bug. It edits the code, runs a check, and says the work is complete. Your next question is whether the requested behavior works **and the surrounding flows still hold up**.

DoneProof gives that question a repeatable workflow. It helps the agent define success before editing, select regressions for the affected flows, and collect current evidence before claiming completion.

**The result is a completion decision backed by the criteria, commands, outputs, and file versions that produced it.**

## What you get

| Capability | What it does for your work |
| --- | --- |
| **Protected acceptance criteria** | Records expected outcomes before implementation and detects changes to those criteria. |
| **Automatic regression selection in the agent workflow** | Directs the agent to trace affected flows, reuse existing tests, and cover meaningful gaps. |
| **Verification proportional to risk** | Keeps local edits focused and expands checks for integrations and critical behavior. |
| **Evidence tied to the code** | Fingerprints declared source, tests, fixtures, and configuration so relevant changes invalidate prior proof. |
| **Required tests actually executed** | Supported counted runners reject empty suites and skipped cases; required test IDs make omitted selections visible. |
| **Rules linked to evidence** | Explicit obligations identify the check responsible for each declared rule. |
| **A clear completion outcome** | Emits `VERIFIED_SUCCESS` after the declared final checks and completion requirements pass. |
| **Reviewable implementation plans** | Maps plan requirements to proof gates and requires a semantic audit before finalizing a plan. |

## A fix can work and still break something

Imagine a greeting function that should return `Hello, Ada`. The new feature passes its acceptance test, but an edit accidentally removes whitespace normalization.

```text
Requested behavior      greet("Ada")     → "Hello, Ada"    PASS
Existing behavior       greet(" Ada ")   → "Hello, Ada"    FAIL
Completion                                                BLOCKED
```

The distributed code example exercises this exact situation. It also checks empty-name rejection. In each broken variant, acceptance can pass while the regression blocks completion. Restoring the behavior allows a fresh verified result. [Explore the runnable example](examples/code)

## Get started

### 1. Install in Codex

Ask Codex to install the skill from this repository.

```text
Use $skill-installer to install the skill at the root of
https://github.com/wilsonferreira23/doneproof
with the name doneproof.
```

Requires **Python 3.10+** on Linux or macOS. The verifier uses Python's standard library. Your project's tests retain their own dependencies.

Use one discovered copy. Keep your existing installation location when updating. Personal installations may use `~/.codex/skills/doneproof` or `~/.agents/skills/doneproof`, depending on the host. Confirm discovery in your Codex environment. [Codex skill documentation](https://learn.chatgpt.com/docs/build-skills)

### 2. Give it a real task

```text
Use $doneproof to fix the redirect after login.
Return the user to the requested page, preserve password recovery,
and validate regressions in the affected authentication flows.
```

Once selected, DoneProof directs the agent to choose and run relevant regressions automatically. Questions, read-only analysis, planning without execution, and trivial prose edits normally skip the workflow.

### 3. Review the evidence

The agent records the outcomes, runs the selected checks, and compares the results with your request. Successful completion requires a current `VERIFIED_SUCCESS`. Missing checks, unresolved failures, and evidence gaps belong in the result you review.

## How it works

```text
Define success → Protect criteria → Implement → Verify + regressions → Review evidence
                                                                           ↓
                                                                   VERIFIED_SUCCESS
```

The agent chooses checks from the request, source, dependencies, and existing harness. The Python CLI runs declared checks and tracks their freshness and dependencies. Saved implementation plans also require an audit against the preserved plan.

| Mode | Use it for | Regression scope |
| --- | --- | --- |
| `light` | Small local changes | Changed behavior, nearby flows, and direct callers. |
| `standard` | Features crossing an integration boundary | Relevant component suites, consumers, and failure paths. |
| `strict` | Authentication, permissions, money, migrations, destructive operations | Affected critical flows, rejection cases, and persisted-state checks where applicable. |

Risk follows the behavior being changed. A one-line permission change can require strict verification.

**One verification cycle per delivery.** A request can involve many files and edits inside one contract. Use focused tests while implementing, then validate the affected flows together when the module or delivery is ready. Full-suite checks follow impact, rather than running after every small edit. If milestone checks remain current, `finish --reuse` avoids rerunning local evidence whose inputs, criteria, runtime and dependencies still match; HTTP and readback checks always refresh.

### Prefer the CLI?

For a small task, prepare acceptance and regression assertions, then protect them before editing product code. Replace `<skill-dir>` with the installed skill's absolute path.

```sh
python3 <skill-dir>/scripts/pod.py init .proof-of-done/my-task/contract.json \
  --input app.py \
  --criterion acceptance.py \
  --run python3 acceptance.py

# Implement the change, then execute the final checks.
python3 <skill-dir>/scripts/pod.py finish .proof-of-done/my-task/contract.json
```

The acceptance file must already exist and can run both acceptance and selected regression checks. Repeat `--input` and `--criterion` before `--run` to cover relevant files. `init` creates a light contract. Standard, strict, and plan workflows use the full contract format. [Contract reference](references/contract.md) · [Extended workflow](references/workflow.md)

### Stronger evidence where the risk warrants it

For supported commands, counted verification records executed tests and rejects empty or skipped selections. Explicit obligations link rules to their checks. Critical flows can add targeted negative controls, property tests or bounded state sequences in isolated fixtures. Each check can declare its evidence method and scope; a test result remains a test result, and a proof of a separate model remains scoped to that model. [Evidence and controls](references/evidence.md)

## Try the examples

From a checkout of this repository, run the package check. It copies examples into temporary directories and exercises successful completion, intentional failures, and recovery.

```sh
python3 scripts/check_package.py
```

| Example | What it demonstrates |
| --- | --- |
| [Basic](examples/basic) | A declared artifact and a failing control. |
| [Counted](examples/counted) | Required test IDs, nonempty execution, linked obligations, and preserved-input regressions. |
| [Code](examples/code) | Acceptance plus preserved-behavior regressions. |
| [Strict plan](examples/strict) | Protected access, guest rejection, saved-state readback, and a plan audit. |

To run the verifier's own test suite as well, use `python3 -m unittest discover -s tests -v`. CI runs checks on Linux and macOS with Python 3.10, 3.11, and 3.14. [View CI results](https://github.com/wilsonferreira23/doneproof/actions)

## What a verified result covers

`VERIFIED_SUCCESS` covers declared criteria and the current evidence snapshot. The agent remains responsible for selecting meaningful tests, identifying affected flows, and reviewing whether tests satisfy the request. The CLI verifies declared evidence, supported execution counts, obligation mappings and freshness. These checks do not determine whether arbitrary assertions express the right requirement.

Input inventories must include relevant source, tests, fixtures, and configuration. Hashes detect changes to declared files. HTTP checks observe external state at the recorded time. Verification commands must be observational or use isolated fixtures. Keep production writes and permanent services outside verification commands.

DoneProof is an instruction-based agent workflow. The host decides when the skill is selected. Its benchmark protocol describes how to measure completion quality, false blocks, and token costs. Historical pilot results remain scoped to the runs they describe. [Evaluation protocol](references/evaluation.md) · [Historical validation](references/validation.md)

<details>
<summary><strong>Installation, updates, and rollback</strong></summary>

Before replacing an installed copy, validate the exact candidate with the test suite and package check. Back up the previous package outside skill discovery directories. Copy `SKILL.md`, `README.md`, `AGENTS.example.md`, `scripts`, `references`, `examples`, and `tests`, and compare hashes after installation. Exclude `.git`, local task proof state, evaluation output, and Python caches. Keep the example contract files shipped under `examples/`.

Run `python3 scripts/pod.py --identity` from the skill directory to record the engine hash and schema. `--version` displays the DoneProof name. Record the source commit separately and confirm that Codex discovers the updated skill. Restart the client if it retains an older entry.

For rollback, restore the backed-up package and verify its hashes. Keep task history. Changes to the verifier can invalidate earlier evidence, so obtain fresh proof for the current version. Archive completed task directories explicitly. The optional project guidance points agents to the installed skill. Cross-project use needs no central task registry. [Project guidance](AGENTS.example.md)

</details>

<details>
<summary><strong>Recovery and platform support</strong></summary>

Task state lives beside its contract. State updates are atomic, and advisory OS locks serialize operations per task. Interrupted commands can leave a RUNNING attempt. Rerun the affected gate and dependent integrations. Preserve a live lock file while its process holds the lock.

Corrupt state or proof blocks completion. Restore a known-good backup or start a new task and execute fresh checks. Every new verification attempt invalidates dependent evidence. `GATE_PASS` and `COVERAGE_COMPLETE` are intermediate outcomes. Finalization emits `VERIFIED_SUCCESS`.

Supported platforms are Linux and macOS with Python 3.10+. Windows, symlink inputs, special-file inputs, and distributed shared-state execution are unsupported. The contract reference documents resource limits, credentials, and check constraints. [Contract reference](references/contract.md)

</details>

<details>
<summary><strong>Migration from schema 2.2</strong></summary>

The current contract format is schema 3. Counted-runner, obligation and evidence-class fields are additive optional fields supported by this engine; older schema-3 engines reject them. Existing contracts without these fields retain their command semantics. Update the engine before using the new fields. Preserve schema 2.2 contracts, plans, ledgers, and history as historical records. Create a new contract in a separate task directory and run fresh proofs. Update integrations that treated any successful `verify` command as global completion.

Use `.proof-of-done/<task-id>/contract.json` with `root: ../..`. Paths resolve from the contract's project root, independently of the command's working directory. For a justified criterion replacement, create a successor task with `supersedes` and preserve the original history. Authorized additions to a plan use immutable `plan_additions` files.

</details>

## Ownership

This package has no license grant. Preserve its existing ownership and licensing status when redistributing it. Publishing a public plugin or granting reuse rights is a separate decision for the owner.
