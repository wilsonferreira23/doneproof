# DoneProof

DoneProof helps a coding agent avoid saying “done” too early.

Writing code or receiving a successful tool response does not prove that the
requested result exists. DoneProof requires an executable check of that result
before the agent can call the work complete.

## In a few words

Imagine the request is:

> “Anyone who is not signed in must be sent to `/login` when opening the dashboard.”

Without DoneProof, an agent can create an authentication file and assume the
job is finished. With DoneProof, it has to verify the real behavior:

```text
open /dashboard while signed out
↓
receive a redirect to /login
↓
save the evidence
↓
only then say the task is done
```

## How it works

Before changing the project, the agent creates a short **success contract**:
a list of things that must be true when the work is finished.

```text
- signed-out visitors are redirected
- the authentication test passes
- the project still builds
```

The contract is locked before implementation starts. If a check fails, the
agent cannot quietly lower the requirement just to declare success.

After the change, DoneProof runs the agreed checks and returns a clear result:

| Result | Meaning |
| --- | --- |
| `VERIFIED_SUCCESS` | Everything that was agreed passed. |
| `VERIFIED_PARTIAL` | Some checks passed, but the gate did not. |
| `FAILED` | The observed result differs from what was expected. |
| `BLOCKED` | An external limitation prevented verification. |

Only `VERIFIED_SUCCESS` allows a completion claim.

## Keep the checks small

DoneProof is designed for long coding loops, so it keeps verification focused:

- `light` mode is the default for normal tasks and allows up to 4 checks per gate.
- `standard` mode is for feature or integration boundaries and allows up to 7 checks.
- `strict` mode is for high-risk work such as authentication, permissions, money, migrations, or destructive operations and allows up to 12 checks.

For a normal task, 2–4 checks are usually enough: prove the requested behavior,
read changed state back when relevant, and run the smallest useful regression
check. Each gate stops at its first failure to avoid wasting context on logs
that do not change the next repair step.

## Installation

Copy this skill into the directory where Codex keeps global skills:

```text
~/.codex/skills/doneproof/
```

Or install it only in one project:

```text
<your-project>/.agents/skills/doneproof/
```

You can also copy the guidance in [`AGENTS.example.md`](AGENTS.example.md)
into your project’s `AGENTS.md`. That reminds Codex to verify important steps.

## First use

1. Before changing code, create `.proof-of-done/contract.json`.
2. Describe the checks the task needs to pass. There is a ready-made
   [example contract](examples/.proof-of-done/contract.json).
3. Lock the contract:

   ```bash
   python3 .agents/skills/doneproof/scripts/pod.py lock .proof-of-done/contract.json
   ```

4. Make the change.
5. Verify the current task gate:

   ```bash
   python3 .agents/skills/doneproof/scripts/pod.py verify .proof-of-done/contract.json --gate task-auth-redirect
   ```

The detailed evidence is saved locally in `.proof-of-done/ledger.json`.
The command-line output stays short so long logs do not crowd the agent’s
context.

## Gates and dependencies

Use a task gate after a bounded change. Use a feature gate after the last task
in a user-visible feature, and a milestone gate only at a real checkpoint.

When you verify a feature or milestone gate, DoneProof also rechecks the gates
listed in its `depends_on` field. This is deliberate: closing a larger piece of
work should confirm that the work it relies on still passes. Do not run those
larger gates after every small task.

If the same gate fails after three reasonable repairs without new evidence,
stop and report the blocker instead of repeating the same loop.

## What kinds of proof does it support?

DoneProof has no extra dependencies and supports three check types:

| Type | Use it for |
| --- | --- |
| `command` | Run tests, a build, or a command your project already uses. |
| `file` | Confirm that a file exists or contains expected text. |
| `http` | Open a URL and inspect the response, such as a redirect. |

For anything else, use `command` to call the tool your project already has.
DoneProof is a gate, not a replacement for your test framework.

## An example check

This check says: “opening the dashboard must redirect to the login page.”

```json
{
  "id": "redirect-when-signed-out",
  "type": "http",
  "url": "http://localhost:3000/dashboard",
  "expect_status": 302,
  "expect_headers": { "location": "/login" }
}
```

This is stronger than checking whether a file called `middleware` exists: it
tests what a person using the system actually receives.

## Core ideas

- **Do not accept “trust me.”** Another agent’s summary is not evidence.
- **Check after changing something.** Create a record? Read it back. Deploy a page? Open it.
- **Fix failures instead of lowering the bar.** The contract stays in place until the task passes.
- **Test what matters.** Do not run every expensive check after every small change.

## Repository layout

```text
SKILL.md                         Instructions for Codex
scripts/pod.py                   Program that runs the checks
examples/.proof-of-done/         Example success contract
AGENTS.example.md                Optional text for AGENTS.md
```

## Research foundations

DoneProof is an engineering adaptation for coding agents, not a direct
implementation of either paper below.

- [From Confident Closing to Silent Failure: Characterizing False Success in LLM Agents](https://arxiv.org/abs/2606.09863) (2026), by Laksh Advani, is the main conceptual foundation. It examines *false success*: an agent claims the task is complete even though the real system state shows failure. It also shows why reasoning and another LLM’s opinion do not replace checking the observed result.
- [Real-Time Detection and Repair of LLM Agent Failures](https://arxiv.org/abs/2608.02464) (2026), by Sunny Dubey, reinforces the architectural direction: deterministic verification, confirmation that required actions occurred, and a loop of verify, detect failure, repair, and verify again.

The locked success contract, SHA-256 lock, task/feature/milestone gates,
fail-fast verifier, and `VERIFIED_SUCCESS` state are DoneProof’s practical
architecture for looping engineering.

## License

This project does not have a license yet. Choose one before distributing the
code or accepting external contributions.
