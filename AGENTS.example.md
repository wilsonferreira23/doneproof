## DoneProof

Use `doneproof` for non-trivial implementation work.

Choose the mode automatically: use `strict` for high-risk work, `standard` for feature/integration boundaries, and `light` otherwise. Keep task contracts small (usually 2-4 checks).

Before implementation:
1. create `.proof-of-done/contract.json`;
2. lock it.

Loop:
`implement -> targeted task gate -> repair if needed -> same gate -> next task`

Run feature gates only when a feature closes and milestone gates only at checkpoints. A selected feature or milestone gate rechecks its declared dependencies.
Never advance on `FAILED`, `BLOCKED`, or `VERIFIED_PARTIAL`.
Never accept an agent summary as evidence.
Persistent/external mutations require read-back verification.
After 3 reasonable failed repairs on the same gate without new evidence, stop thrashing and report the blocker.
