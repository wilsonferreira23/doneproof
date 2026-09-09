## DoneProof

For nontrivial implementation, read the installed DoneProof SKILL.md before
changing product code. Use a separate contract directory per task and lock
meaningful criteria before implementation. Include relevant input and criterion
files. Verify at task/feature boundaries and repair failures before advancing.

Only `pod.py finalize` returning `VERIFIED_SUCCESS` authorizes completion.
For large plans, preserve the original plan and additions, cover every outcome,
then perform and record a semantic audit tied to current proofs. `GATE_PASS` and
`COVERAGE_COMPLETE` alone do not authorize a completion claim.

Read-back must confirm mutations. Keep checks observational or isolated; do not
repeat a production write to refresh evidence. Do not weaken tests after failure.
