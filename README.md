# DoneProof 2.2

DoneProof is a lightweight deterministic completion gate for coding agents.

It addresses two different failure modes:

1. **False success** — the agent says work is done without proving the behavior.
2. **Plan omission** — a long implementation loop finishes while parts of the original plan were never implemented or verified.

DoneProof 2.2 keeps the low-token 2.1 verifier and adds **Plan Coverage**.

## Core loop

```text
original plan
  ↓
requirements R1..Rn
  ↓
implement → targeted gate → repair if needed
  ↓
final integration gate
  ↓
coverage
  ↓
one semantic audit against the original plan
  ↓
missing item? → extend → implement → verify → final gate → coverage
  ↓
VERIFIED_SUCCESS coverage=100%
```

`coverage=100%` means every extracted requirement has executable PASS evidence and
the final integration gate was run after the latest requirement proof. It is
strong evidence, not mathematical certainty.

## Low-token design

DoneProof deliberately avoids a permanent second-agent judge.

- task gates stay small;
- checks fail fast;
- CLI output is concise;
- detailed evidence stays in files;
- semantic plan comparison happens once at the end, not after every task;
- a semantic audit is repeated only if something new was added or repaired.

## Install

Project-local:

```text
<project>/.agents/skills/doneproof/
```

Or copy it into your global Codex skills directory.

Optionally merge `AGENTS.example.md` into the project's `AGENTS.md`.

## Normal task

Create and lock:

```bash
python3 .agents/skills/doneproof/scripts/pod.py lock .proof-of-done/contract.json
```

Verify only the current gate:

```bash
python3 .agents/skills/doneproof/scripts/pod.py verify .proof-of-done/contract.json --gate task-id
```

Only `VERIFIED_SUCCESS` permits a completion claim.

## Large plan

Preserve the exact original plan:

```text
.proof-of-done/plan.md
```

Add these fields to the contract:

```json
{
  "mode": "standard",
  "plan_path": ".proof-of-done/plan.md",
  "requirements": [
    {
      "id": "R1",
      "text": "Signed-out users are redirected to /login",
      "gate": "task-auth-redirect"
    }
  ],
  "final_gate": "module-final",
  "gates": []
}
```

Each requirement points to the gate that proves it.

After all tasks, run the final gate and then:

```bash
python3 .agents/skills/doneproof/scripts/pod.py coverage .proof-of-done/contract.json
```

A successful result looks like:

```text
VERIFIED_SUCCESS coverage=100% requirements=47/47 final_gate=module-final
```

## Final semantic audit

After deterministic coverage reaches 100%, the coding agent performs one
adversarial comparison:

- original `.proof-of-done/plan.md`;
- requirement matrix;
- implementation;
- verification evidence.

The instruction is: **assume something may be missing and try to find a
requested outcome that is absent, partial, or not actually proved.**

If the audit finds an omitted requirement, add it and any new gate without
changing old criteria, then run:

```bash
python3 .agents/skills/doneproof/scripts/pod.py extend .proof-of-done/contract.json
```

`extend` is monotonic: it rejects deletion or modification of existing
requirements/gates and rejects lowering the verification mode.

Then implement the gap, verify its gate, rerun the final gate, and rerun
coverage.

## Why the final gate must be last

If a new requirement is verified after the final gate, DoneProof returns:

```text
INCOMPLETE_PLAN_COVERAGE ... final_gate=module-final:rerun-required
```

This prevents old integration evidence from being used to approve newly changed
work.

## Plan integrity

When `plan_path` is present, DoneProof hashes the original plan at lock time.
Changing the plan file afterward blocks verification.

## Modes

| Mode | Intended use | Max checks/gate |
| --- | --- | ---: |
| `light` | normal tasks | 4 |
| `standard` | features/integrations | 7 |
| `strict` | auth, permissions, money, migrations, destructive/high-risk work | 12 |

The agent chooses the mode automatically. Use the smallest useful proof.

## Supported checks

DoneProof intentionally supports only:

- `command`
- `file`
- `http`

`command` can call the project's existing Playwright, Vitest, pytest, build,
typecheck, database probes, Docker commands, mobile tests, migrations, or custom
verification scripts.

## State files

```text
.proof-of-done/lock.json
.proof-of-done/ledger.json
.proof-of-done/history.json
.proof-of-done/coverage.json
```

The model normally needs only the concise CLI output. Detailed evidence is read
only when debugging.

## Repository layout

```text
SKILL.md
scripts/pod.py
examples/.proof-of-done/contract.json
examples/.proof-of-done/plan.md
AGENTS.example.md
```

## Research foundations

DoneProof is an engineering adaptation, not a direct implementation of these
papers:

- **From Confident Closing to Silent Failure: Characterizing False Success in
  LLM Agents** — https://arxiv.org/abs/2606.09863
- **Real-Time Detection and Repair of LLM Agent Failures** —
  https://arxiv.org/abs/2608.02464

## License

This repository currently has no license. Add one before relying on standard
open-source redistribution/contribution expectations.
