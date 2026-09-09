# Agent evaluation

This runner requires Python 3.11+ and an authenticated Codex CLI. The verifier
itself requires Python 3.10+ and no account. Running agent episodes consumes the
account's normal usage. A completed protocol contains 36 pilot or 360 final
episodes, as authorized in the implementation plan.

`scripts/evaluate.py` freezes the corpus, reference/candidate skill copies, model,
reasoning setting, timeout, CLI version and evaluation thresholds. It disables
discovered optional skills for each child through invocation-only configuration;
the requested DoneProof copy is explicitly read inside its isolated workspace.
It does not change the user's saved configuration or create persistent sessions.
The default model/settings are taken from the user's existing configuration.

The three conditions use identical requests and raw files: ordinary testing,
DoneProof 2.2 and the candidate. Each result is graded by a controller-owned oracle
outside the agent's workspace. Final structured output records whether the agent
claims completion; the oracle independently determines actual correctness.

Corpus JSON: `{"provenance": "...", "cases": [...]}`. Every case has `id`,
`category` (`normal`, `integration`, `strict`, `plan`, `operational`), `request`,
`files` (relative path to starting text) and `oracle` (Python code receiving the
workspace as `sys.argv[1]`; nonzero means an unmet requested outcome). Keep oracles
deterministic and independent of the agent's extracted contract. Freeze 12 pilot
tasks or 60 held-out final tasks, with unique IDs. Do not count mere parameter
variants as evidence of broad real-world generalization. Review oracle quality
and corpus provenance before interpreting a score.

```sh
python3 scripts/evaluate.py freeze CORPUS.json evaluation/pilot --baseline /path/to/doneproof-2.2 --stage pilot
python3 scripts/evaluate.py run evaluation/pilot --workers 3
python3 scripts/evaluate.py report evaluation/pilot
```

Final uses `--stage final` and `evaluation/final`, with two executions per task.
`report --require-pass evaluation/final` rejects missing episodes, infrastructure
errors, observed false completion, <90% correct completion, regressions against
the best baseline, >5% false blocks, or >20% median normal-task token overhead.
Pilot results cannot satisfy final efficacy. Publish absolute counts and the
task-clustered uncertainty interval, not just percentages. Compare total executor
input+output tokens, including cached tokens, using paired task/repetition values.
Report durations separately; timing and tokens are not interchangeable.

Full JSONL events, answers, oracle results and episode metrics are retained.
Completed episodes can be resumed without rerunning. Interrupted directories are
not silently overwritten: preserve the failure and investigate before a new
evaluation. Protocol or frozen skill changes invalidate reuse. The report does
not grant 9/10 by itself: R01–R16 and an external review of corpus quality also
need to pass. Training-set familiarity and hand-authored synthetic cases limit
what any benchmark result can establish.

CLI behavior was checked against the installed executable and the official
[non-interactive mode documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

Final corpora include `requirement_ids` for each case. The external oracle prints one JSON object containing `requirements`, a mapping from those IDs to booleans, and exits zero only if all are true. Missing outcome coverage cannot pass merely because the process exits zero. SIGINT/SIGTERM stops active executors and leaves their interrupted results; pending episodes are not started. Category filtering is for development diagnostics and never makes an incomplete run qualify as final efficacy.

An executor infrastructure error stops scheduling further work and interrupts active executors, retaining every result and log. Investigate before starting another frozen evaluation; failures are never silently dropped or relabeled as successful episodes.

For final candidate episodes declared complete, the controller checks the supplied skill is unchanged and revalidates the saved completion with `finalize` before running the external oracle. It does not repeat product tests. Plan tasks must preserve the raw request as their plan and use a plan contract; strict tasks must use strict mode; integration tasks use standard or strict. Missing/stale proof or skipped workflow blocks release even when product assertions happen to pass. This controller work is outside the measured executor token count and duration, as are all external oracle checks.

External grading runs on a fresh copy of the completed solver artifacts, preserving the original workspace and its pre-grading completion evidence. The workspace-write CLI configuration and explicit instruction not to read outside the solver workspace are not claimed to be a hostile-solver sandbox; this evaluation concerns ordinary errors and omissions, not a solver deliberately seeking hidden grader files.
