# Changelog

## 2.2.0

- Added Plan Coverage for long implementation loops.
- Added immutable original-plan hashing via `plan_path`.
- Added requirement-to-gate coverage matrix and `coverage` command.
- Added monotonic `extend` for newly discovered requirements.
- Requires the final gate to be rerun after newly verified requirements.
- Preserved lightweight targeted verification for normal tasks.
