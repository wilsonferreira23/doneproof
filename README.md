<div align="center">

# DoneProof

### Know what was checked before you call it done.

A Codex skill that helps your AI check the work it delivers.

[![Checks](https://github.com/wilsonferreira23/doneproof/actions/workflows/tests.yml/badge.svg)](https://github.com/wilsonferreira23/doneproof/actions/workflows/tests.yml)

[Get started](#get-started) · [See an example](#a-simple-example) · [How it works](#how-it-works)

</div>

---

You ask your AI to fix something. It changes the code and replies, **“Done.”**

But did it check what you asked for? Did the change break something that used to work?

**DoneProof helps the AI answer those questions before finishing your request.** It guides the AI to write down what success means, make the change, check the affected parts, and show you the results.

You describe the result you want. The agent handles the verification steps.

## A simple example

Imagine you ask:

> After login, take users back to the page they wanted to open.

The new redirect works. But a related change accidentally breaks password recovery.

Checking only the redirect would miss that problem. DoneProof directs the agent to check the related behavior too:

| What needs to work | Example result |
| --- | --- |
| Login returns the user to the requested page | Passed |
| Incorrect passwords are still rejected | Passed |
| Password recovery still works | Failed |

**There is still work to do.** The agent should fix the failure or clearly report what remains unresolved.

Checking that existing behavior still works is called a **regression check**. DoneProof helps the agent choose these checks based on the parts the change can affect.

This is an illustration. For a small runnable demonstration, the [greeting example](examples/code) shows a change that passes its new test but breaks existing behavior.

## How it works

1. **Understand the request.** Record what should work when the task is finished, including existing behavior that needs to keep working.
2. **Make the changes.** Work on the relevant files, using focused checks along the way when helpful.
3. **Check the delivery.** Run the checks selected for the affected parts. A higher-risk change needs stronger verification.
4. **Show the outcome.** Explain what passed, what failed, and what could not be checked.

The expected outcomes are protected before implementation, so making a failing check easier is not a valid way to finish. Results are also tied to the version of the code that was checked. Relevant changes can make an earlier result out of date.

## Will it check every line and slow everything down?

**Verification is organized around a request, module, or meaningful stage of work.** One request can involve many files and many edits inside the same verification cycle.

The agent can run focused tests while working, then check the delivery when it is ready. The full test suite is used when the impact calls for it, rather than after every small edit.

Previously passing local checks can be reused when the code and other relevant inputs still match. Checks affected by changes must run again. Observations of websites or saved state are refreshed because that state can change independently.

| Your request | How much checking makes sense? |
| --- | --- |
| Correct a typo in a description | A focused review; no artificial tests. |
| Change one calculation | Check the calculation and the nearby behavior it can affect. |
| Connect two parts of an application | Check that they work together, including relevant failure cases. |
| Change login, permissions, payments, or data deletion | Check allowed actions, rejected actions, and saved results where applicable. |

A small edit can still carry high risk. What the change does matters more than how many lines it touches.

## Get started

### 1. Install the skill

Paste this into Codex:

```text
Use $skill-installer to install the skill at the root of
https://github.com/wilsonferreira23/doneproof
with the name doneproof.
```

The verifier requires Python 3.10+ on Linux or macOS. It uses Python's standard library; your project's tests may have their own requirements. Codex needs to discover the installed skill. [Skill installation documentation](https://learn.chatgpt.com/docs/build-skills)

### 2. Ask for your change

You can speak normally. For example:

```text
Use $doneproof to fix the redirect after login.
Return users to the page they originally requested,
and check that password recovery still works.
```

You do not need to prepare terminal commands to use the skill. Once selected, it guides the agent to choose and run the relevant checks. Ordinary questions, research, and small prose edits normally do not need this workflow.

### 3. Read the result

Look for an explanation of:

- What was changed.
- What was actually checked.
- Whether any relevant checks failed or could not run.

A successful verification produces `VERIFIED_SUCCESS`. That means the recorded requirements have current passing evidence. It does not mean every possible bug has been ruled out.

## What makes the checks useful?

DoneProof helps keep the expected result stable while the code changes. It records which checks support each declared rule and whether those results still apply to the current code.

For supported test tools, it also rejects empty test runs, skipped tests in the selected run, and missing required test cases. More demanding tasks can include checks that deliberately exercise a failure or explore combinations of actions in a disposable test environment.

The agent still needs to choose meaningful checks. A passing test that asks the wrong question cannot establish that your request was fulfilled. DoneProof supports that review; it does not replace it.

## Want the technical details?

The day-to-day instructions are in [SKILL.md](SKILL.md). The sections below are for people who want to run the verifier directly, maintain an installation, or understand its limits.

<details>
<summary><strong>Commands, verification modes, and examples</strong></summary>

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

For previously verified local work, `finish <contract> --reuse` reuses evidence only while its declared inputs, criteria, runtime, and dependencies still match. HTTP and readback checks always refresh. Other commands observing mutable external state need a fresh `finish` or an appropriate readback check.

The modes are `light` for local behavior changes, `standard` for work crossing an integration boundary, and `strict` for critical changes such as permissions or money. [Full workflow](references/workflow.md)

Counted execution supports unittest and Bun. Required case IDs currently use verbose unittest output. Other harnesses and custom scripts need explicit assertions or adapters for execution and outcomes. Obligation mappings and evidence methods are described in [Evidence and controls](references/evidence.md). A declared evidence label does not turn a test into a mathematical proof.

Try the distributed examples in disposable copies:

```sh
python3 scripts/check_package.py
```

Examples: [basic artifact](examples/basic), [acceptance and regressions](examples/code), [required tests and rules](examples/counted), [strict implementation plan](examples/strict).

To run the verifier's own tests, use `python3 -m unittest discover -s tests -v`. GitHub checks Linux and macOS with Python 3.10, 3.11, and 3.14. [See CI results](https://github.com/wilsonferreira23/doneproof/actions)

The [evaluation protocol](references/evaluation.md) describes how to measure quality and added cost. [Historical validation](references/validation.md) applies only to its recorded runs; no fixed speed improvement is promised.

Verification commands must observe state or use isolated fixtures. Relevant source, tests, fixtures, and configuration must be included in the recorded inputs. Keep production writes and permanent services outside verification commands. The host controls when the skill is selected.

</details>

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
