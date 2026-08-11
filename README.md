# DoneProof

**Completion is a state proved by evidence, not a conclusion produced by an agent.**

DoneProof is a lightweight Codex skill for preventing false success: an agent
claiming a task is finished because it changed code, ran a command, or received
a successful tool response. It requires a locked success contract and a
deterministic verifier before a task can be reported as complete.

## What it does

DoneProof turns a request into observable checks, locks those checks before
implementation, and evaluates them through gates:

```text
plan → lock contract → implement → task gate → repair → feature gate → milestone gate
```

- A contract is hashed when locked, so failed criteria cannot be silently
  weakened during a repair loop.
- Checks can run commands, inspect files, or make HTTP requests.
- Results are written to a local evidence ledger.
- A successful write is not proof: state-changing work should be read back and
  compared with the expected result.

## Installation

Copy this repository's `doneproof` directory to your Codex skills directory:

```text
~/.codex/skills/doneproof/
```

Or install it for one project:

```text
<project>/.agents/skills/doneproof/
```

Optionally merge the guidance in [`AGENTS.example.md`](AGENTS.example.md) into
your project's `AGENTS.md` to make the gates part of the engineering workflow.

## Quick start

Before changing implementation files, create a success contract at
`.proof-of-done/contract.json`. The included
[`example contract`](examples/.proof-of-done/contract.json) demonstrates task,
feature, and milestone gates.

Lock the contract:

```bash
python3 .agents/skills/doneproof/scripts/pod.py lock .proof-of-done/contract.json
```

After implementing the task, verify the relevant gate:

```bash
python3 .agents/skills/doneproof/scripts/pod.py verify .proof-of-done/contract.json --gate task-auth-redirect
```

The verifier writes its evidence to `.proof-of-done/ledger.json` and returns
one of these states:

| State | Meaning |
| --- | --- |
| `VERIFIED_SUCCESS` | Every required check passed. |
| `VERIFIED_PARTIAL` | Some checks passed, but the requested gate did not. |
| `FAILED` | Observed behavior differs from the contract. |
| `BLOCKED` | Verification could not run because of an external constraint. |

Only `VERIFIED_SUCCESS` permits a completion claim.

## Supported checks

The bundled verifier supports three intentionally small, dependency-free check
types:

| Type | Use it to |
| --- | --- |
| `command` | Run the project's existing tests, build, linter, migration checker, or scripts. |
| `file` | Check that a file exists or contains the expected text. |
| `http` | Exercise an endpoint and assert its status, headers, or response body. |

For everything else, use `command` to call the tooling the project already
uses. DoneProof does not need to replace your test runner.

## Contract example

```json
{
  "id": "unauthenticated-redirect",
  "type": "http",
  "url": "http://localhost:3000/dashboard",
  "expect_status": 302,
  "expect_headers": { "location": "/login" }
}
```

This is stronger than checking that a middleware file exists: it observes the
behavior a user actually receives.

## Principles

- **No transitive trust:** another agent's summary is not evidence.
- **Read after write:** verify persistent or external state after changing it.
- **Repair, don't weaken:** preserve failure evidence and rerun the locked
  contract after a fix.
- **Use the smallest relevant gate:** do not run expensive unrelated checks.

## Repository layout

```text
SKILL.md                         Codex instructions
scripts/pod.py                   Deterministic verifier
examples/.proof-of-done/         Sample contract
AGENTS.example.md                Project-level workflow guidance
```

## License

No license has been selected for this project yet. Add one before distributing
or accepting external contributions.
