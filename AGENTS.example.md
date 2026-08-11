## Completion gates

Use the `doneproof` skill for implementation work.

Before implementation, create and lock the Success Contract.

No task, feature, or milestone may be considered complete unless its applicable
DoneProof gate returns VERIFIED_SUCCESS.

Never trust another agent's success summary as verification.

For looping work:

task → task gate → repair until pass → next task

feature complete → feature gate → repair until pass → checkpoint

milestone complete → milestone gate → repair until pass → next milestone

Do not advance the loop on FAILED, BLOCKED, or VERIFIED_PARTIAL.
