# DoneProof 2.1

DoneProof is a minimal deterministic completion gate for coding agents.
Its goal is simple: an agent may only say a task is done after observable
checks prove the requested outcome.

Version 2.1 is optimized for looping engineering and lighter coding models:
less prompt text, fewer checks, targeted gates, fail-fast execution, and concise
CLI output.

## Why 2.1

Long coding loops fail badly when an agent says `done` too early and the next
steps build on that false assumption. DoneProof turns completion into an
external gate:

```text
implement -> verify -> PASS -> continue
                  \-> FAIL -> repair -> verify again
```

## Design goals

- **Low token overhead**: `SKILL.md` is intentionally short.
- **Deterministic evidence**: the verifier, not agent prose, owns the result.
- **Targeted verification**: `--gate` is required; broad verification is not the default.
- **Fail fast**: stop at the first failed check in a gate.
- **Small contracts**: LIGHT mode allows at most 4 checks per gate.
- **No success-criteria drift**: contracts are locked with SHA-256 before implementation.
- **No transitive trust**: another agent saying “tests passed” is not evidence.

## Modes

| Mode | Use | Max checks/gate |
| --- | --- | ---: |
| `light` | Default for normal tasks | 4 |
| `standard` | Feature/integration boundary | 7 |
| `strict` | Auth, permissions, money, migrations, destructive/high-risk work | 12 |

Do not choose a heavier mode merely because it sounds safer. Verification cost
should be proportional to failure risk.

## Minimal success contract

For a normal task, usually 2–4 checks are enough:

1. prove the requested behavior/output;
2. if state changed, read it back and compare;
3. run the smallest relevant regression check.

Example:

```json
{
  "version": "2.1",
  "mode": "light",
  "gates": [
    {
      "id": "task-auth-redirect",
      "level": "task",
      "checks": [
        {
          "id": "auth-test",
          "type": "command",
          "argv": ["npm", "test", "--", "auth"]
        },
        {
          "id": "redirect-behavior",
          "type": "http",
          "url": "http://localhost:3000/dashboard",
          "expect_status": 302,
          "expect_headers": {"location": "/login"}
        }
      ]
    }
  ]
}
```

## Install

Project-local skill:

```text
<project>/.agents/skills/doneproof/
```

Or copy it into your global Codex skills location.

Optionally merge `AGENTS.example.md` into your project `AGENTS.md` so the loop
always respects DoneProof gates.

## Usage

Create `.proof-of-done/contract.json`, then lock it before implementation:

```bash
python3 .agents/skills/doneproof/scripts/pod.py lock .proof-of-done/contract.json
```

Verify only the current gate:

```bash
python3 .agents/skills/doneproof/scripts/pod.py verify .proof-of-done/contract.json --gate task-auth-redirect
```

Possible results:

- `VERIFIED_SUCCESS`
- `VERIFIED_PARTIAL`
- `FAILED`
- `BLOCKED`

Only `VERIFIED_SUCCESS` permits a completion claim.

Detailed evidence is stored in:

```text
.proof-of-done/ledger.json
```

The CLI intentionally prints only a concise summary so large logs do not flood
the model context.

## Supported checks

DoneProof deliberately stays small:

- `command`
- `file`
- `http`

Use `command` to call the project's existing tooling: Playwright, Vitest,
pytest, TypeScript, builds, migrations, database probes, Docker, mobile tests,
or custom scripts. DoneProof is a gate, not a replacement test framework.

## Loop policy

```text
task -> task gate -> repair until pass -> next task
feature complete -> feature gate -> checkpoint
milestone complete -> milestone gate -> next milestone
```

If the same gate fails after 3 reasonable repair attempts without materially
new evidence, stop thrashing and report the blocker instead of burning tokens.

## Research foundations

DoneProof is inspired by two 2026 papers:

- **From Confident Closing to Silent Failure: Characterizing False Success in LLM Agents**  
  https://arxiv.org/abs/2606.09863
- **Real-Time Detection and Repair of LLM Agent Failures**  
  https://arxiv.org/abs/2608.02464

DoneProof is not a direct implementation of either paper. The locked success
contract, task/feature/milestone gates, fail-fast verifier, and looping policy
are an engineering adaptation for coding agents.
