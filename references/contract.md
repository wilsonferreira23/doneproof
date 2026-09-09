# Contract reference — schema 3

Use Python 3.10+ on Linux or macOS. Each contract lives in its own state directory,
for example `.proof-of-done/task-a/contract.json`. All check paths and plan paths
are relative to `root`; `root` is relative to the contract directory, never cwd.
Keep state outside the product inputs. The CLI serializes operations per task.

Required fields:

| Field | Meaning |
|---|---|
| `schema_version` | Integer `3`. |
| `task_id` | Stable `[A-Za-z0-9][A-Za-z0-9_-]{0,79}` identifier. |
| `root` | Project path, usually `../..` for the layout above. |
| `kind` | `task` or `plan`. A plan requires the fields below. |
| `mode` | `light`, `standard`, `strict`; at most 4, 7, 12 checks/gate. |
| `gates` | Nonempty list of gates. All must contribute to final or a requirement. |
| `final_gate` | Existing gate ID. Its result must be current and follow all requirement proofs. |

Plans additionally require `plan_path` and a nonempty `requirements` list.
Each requirement has exactly `id`, `text`, `gate`, `source`; `source` is a literal
excerpt from the original plan or an authorized addition. It is an origin anchor,
not a semantic proof. `plan_additions` optionally lists immutable addition files.
Existing gates, requirements and plan additions cannot be removed or changed by
`extend`. New requirements mapped to old gates invalidate those gates, too.

Optional `mutations`: a list of `{ "outcome": "Persisted outcome", "gate": "g",
"check": "readback-check" }`. Each mapping must refer to a `readback` purpose.
Optional `supersedes`: `{ "task_id": "old-task", "contract_sha256": "old digest",
"reason": "Authorized scope change or justified criterion correction" }` for a
new task directory. The reference is attribution, not an authorization service.

## Gates and inputs

Each gate requires `id`, `level` (`task`, `feature`, `milestone`), `inputs`,
`criteria`, `checks`. Optional fields: `depends_on`, `excludes` (string lists).
Gate/check/requirement IDs follow the same identifier rule as task IDs.

`inputs` lists product files or directories recursively. Missing files are
recorded as absent; additions and deletions inside declared directories are
detected. Include relevant build/test configuration and data. `criteria` lists
explicit acceptance files, fixtures and configurations protected at lock time;
they must already exist. Inline Python `-c` assertions are protected by the JSON.
Other command checks require at least one protected criterion file. The CLI
cannot automatically discover every transitive dependency of an arbitrary tool.

`excludes` contains explicit relative paths to generated outputs only. The state
directory is always excluded. Symlinks and special files are rejected. No glob
syntax; use directories to include future source files. Max 100,000 inventory
entries and 256 MiB per input file. Checks may not modify their inputs or protected
criteria. Isolated tests should write to temporary directories outside the input
inventory. Do not exclude relevant source files to work around stale evidence.

Modes require proof purposes across applicable gates: all modes need `behavior`;
standard and plans require `integration` on final; strict additionally requires
`negative`. Mutations require mapped `readback`. These are structural obligations;
inspect the actual assertions, selected test count and negative controls.

## Checks

Every check has `id`, `type`, `purpose`. Optional `timeout` is positive seconds;
optional `max_bytes` is a positive integer up to 16 MiB (default 1 MiB). Unknown
fields and duplicate JSON keys are rejected. A resource limit blocks/fails rather
than approving truncated evidence.

`command`: required `argv` (nonempty strings), `expect_exit` (integer), `effect`
(`observe` or `isolated_test`). Optional `cwd`, `stdout_contains`, `env_from`.
`env_from` maps child variable names to existing parent variable names. The
command inherits the current environment and receives `PYTHONDONTWRITEBYTECODE=1`.
Execution uses no implicit shell. Timeout defaults to 120 seconds, and the process
group is terminated on timeout, interruption or completion. Do not use checks to
start persistent services. Output capture has a combined byte cap; proof retains
exit status, stream digests, byte counts and short output tails. If runtime or
environment versions materially affect the result, declare them as controlled
inputs or check them explicitly; environment inheritance is not a version pin.
Each proof also records the verifier digest, Python version, resolved command
executables and hashes of explicitly declared `env_from`/`headers_env` values.
Changes invalidate that proof without storing the environment secrets themselves.
Undeclared inherited environment and transitive runtime dependencies still need
explicit inventory or version checks when relevant.

`file`: required `path`. Optional `exists` (boolean, default true), `contains`,
`equals`, `sha256`. Expected absence cannot be combined with content expectations.
Actual hash, size, permissions and relevant content sample are recorded. Existence
is a legitimate artifact check but does not prove application behavior by itself.

`http`: required `url`, `expect_status` (integer). Optional `method` (GET/HEAD),
`headers`, `headers_env`, `expect_headers`, `response_contains`. Credentials in
URLs or literal sensitive request headers are rejected; use `headers_env` mapping
header names to environment variable names. Redirects are not followed. Actual
compared headers, body digest/sample and observation time are retained. Default
timeout is 15 seconds. HTTP gates must be in final's dependency closure so final
reruns their observations. A HTTP success response to a write is not read-back.

Never embed secrets in argv, fixtures, contracts or expected response bodies.
Known secret environment values and sensitive HTTP evidence headers are redacted,
but arbitrary application output cannot be guaranteed free of secrets.

## State and exit codes

State resides beside the contract: `state.json`, `revisions/`, `proofs/`,
`coverage.json`, `audits/`, `completion.json`, `.pod.lock`. `state.json` is an
atomic index; proof files are written before their reference is published.
Advisory OS locks serialize CLI operations. Do not edit these generated files.
Missing/corrupt evidence blocks; a RUNNING attempt after a killed process is not
a PASS. Rerun the affected gate to recover from interruption. Never reset history
to reuse a previous success. Separate contracts must use separate directories.

| Command | Successful output | Meaning |
|---|---|---|
| `lock` | `LOCKED` | Criteria and original plan preserved. |
| `extend` | `EXTENDED` | Additions accepted; affected proofs/final invalidated. |
| `verify --gate ID` | `GATE_PASS` | This gate and executed dependencies passed. |
| `coverage` | `COVERAGE_COMPLETE coverage=100%` | Declared outcomes have coherent current proofs and final is current. |
| `finalize [--audit FILE]` | `VERIFIED_SUCCESS` | Completion authorized for this evidence snapshot. |

Exit 0 means command-local success, 1 failed check/incomplete coverage, 2 blocked
or invalid operation. Completion requires `finalize` exit 0, not any exit 0.
No cached completion is an everlasting approval. Rerun validation after changes.

## Audit

After final and coverage pass, read the original plan/additions and the proof
files named by `coverage.json`. Write a separate audit JSON, copying the identity
fields from coverage and supplying your actual semantic assessment:

```json
{
  "schema_version": 3,
  "revision": 1,
  "contract_sha256": "copy from coverage",
  "snapshot": "copy from coverage",
  "plans_sha256": "copy from coverage",
  "plan_review": "Explain how you checked the whole plan for omissions.",
  "gaps": [],
  "requirements": [
    {
      "id": "R1",
      "source": "Exact source from the requirement",
      "proof": "Exact proof ID from coverage",
      "assessment": "Explain which observed assertion proves this outcome."
    }
  ]
}
```

Do not fill this with automatic positive text. Report gaps, repair them, regenerate
affected evidence and reassess. The CLI checks identity, completeness and freshness
of the audit record; it cannot determine the truth of the reviewer's prose.

## Light-task initializer

`init CONTRACT --input PATH --criterion PATH --run COMMAND...` creates and locks a light task in the current project. Repeat input/criterion flags before --run. Acceptance files must already exist; the contract must not exist. The task ID is its parent directory name. Use `.proof-of-done/<task-id>/contract.json`. The generated gate ID is `final`, with behavior purpose and isolated-test effect. Review command effects as usual. Product inputs, criterion hashes and all regular freshness checks are unchanged. Plans, standard/strict modes and HTTP/file checks use the full contract workflow.

For a justified correction to a light task's criteria, preserve the old criterion file and use a new filename and task directory. Add `--supersedes OLD_CONTRACT --reason 'specific correction'` before `--run`. The previous task must be locked, light, in the same project, and retain its protected contract and criteria. The initializer records its identity and contract hash without modifying its history. The new task starts without usable proofs and needs its own verification and finalization. This shortcut cannot replace standard/strict tasks or plans.
