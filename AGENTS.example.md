## DoneProof

Use `doneproof` for non-trivial implementation work.

Choose mode automatically: `strict` for high-risk work, `standard` for feature/integration boundaries, `light` otherwise. Keep task gates small.

For large plans:
1. preserve the original plan in `.proof-of-done/plan.md`;
2. map every required outcome to a stable requirement ID and proof gate;
3. lock before implementation.

Loop:
`implement -> targeted gate -> repair -> same gate -> next task`

Never advance on `FAILED`, `BLOCKED`, or `VERIFIED_PARTIAL`.
Mutations require read-back verification.
After 3 failed repairs without new evidence, stop thrashing.

Before declaring a large plan complete:
1. run its final gate;
2. run `pod.py coverage`;
3. do one semantic audit comparing the original plan to the coverage matrix;
4. if a missing requirement is found, append it with `pod.py extend`, implement/verify it, rerun the final gate and coverage.

Completion requires final-gate `VERIFIED_SUCCESS` and `coverage=100%`.
