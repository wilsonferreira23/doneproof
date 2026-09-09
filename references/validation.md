# Validation of 3.0.0-rc1

Recorded 2026-09-08. This is a candidate release, not a demonstrated 9/10 result.

- 55 automated tests passed on native macOS/Python 3.14 and Linux containers with Python 3.11 and 3.10.
- Basic, code and strict examples pass; incorrect output, incorrect authorization and absent persistence prevent completion in the package checks.
- An independent agent completed a small tags task using the skill. The resulting code was separately checked and its gate reexecuted against the current engine.
- Initial developmental pilot: 12 synthetic tasks × 3 conditions = 36 actual agent episodes. All three conditions completed 12/12 correctly, without observed false completion or false blocking. Candidate normal-task median token overhead was 110.5% over ordinary tests.
- After simplifying the workflow, a focused diagnostic repeated the four normal tasks across the same three conditions: 12 actual episodes, all correct. Median normal-task token overhead was 30.6%, still above the proposed 20% threshold. These four tasks were used for development, not held-out validation.
- The frozen 60-task, 360-episode final evaluation has not run. R17/R18 remain unfulfilled. No relative reduction in false completion was demonstrated because both references also had zero observed false completions in the pilot.

Token counts include measured executor input and output tokens, including cached input. Different developmental runs do not establish that the entire measured cost difference was caused by the documentation edit. With only four normal tasks, cost estimates remain uncertain.

The engine and SKILL.md used in the focused diagnostic match this candidate. The package checker subsequently gained additional negative controls; validation notes were added after the frozen run. Raw results, frozen copies, oracles and logs are in the implementation delivery, separate from the installed skill to avoid loading or shipping generated workspaces as instructions.

The CI workflow is provided but has not run on a remote repository. Linux checks used local Docker containers. These are validation results for this version, not a permanent guarantee for future changes.
