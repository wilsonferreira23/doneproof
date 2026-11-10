# Evidence, obligations and controls

Use this reference when selected tests must be counted, a critical rule needs an explicit evidence mapping, or generated/property/formal checks need a precise scope. Keep one contract per coherent request, module or deliverable stage. Protect the selection before implementation and validate at the delivery boundary; these features do not require a contract or full suite for each edit.

## Count the selected tests

A command check may declare `runner: unittest` or `runner: bun`, with `min_tests` (positive integer, default 1). The runner adapter requires an unambiguous successful summary and a nonempty execution count. Skips and expected failures in that selected command cannot satisfy its evidence. Separate intentionally optional cases from the command that represents mandatory coverage; do not hide a required case by excluding it.

For unittest, `required_tests` lists exact test IDs and requires verbose output. This detects a required case missing from the selected execution even when other tests pass. Include the tests, fixtures, configuration and source in the gate's input inventory. Put expected outcomes and required selections in protected criteria. Counts alone cannot show that the assertion exercises the intended behavior.

`init` recognizes Python `-m unittest` and `bun test` commands and enables the corresponding counted runner. For a hand-written contract, declare the runner explicitly. Other harnesses and standalone acceptance scripts retain command semantics; their protected acceptance must verify actual execution and outcomes. Do not label arbitrary commands as supported test runners merely to obtain a counter. File and HTTP checks have their own evidence and need no artificial test count.

## Link obligations to checks

An optional contract `obligations` list gives each rule an `id`, `text`, `gate` and `check`. The engine validates the references and requires current passing evidence for the mapped check. Protected criteria define the rule's premises, allowed and rejected outcomes, and selected assertions. The map records responsibility; it cannot establish that arbitrary test code correctly expresses the rule.

For a plan, retain its original requirements and source excerpts. Obligations can identify supporting invariants without rewriting the user's preserved plan. Do not replace a missing requirement with a convenient weaker property.

This example uses a project containing `app.py`, `tests/test_math.py` and protected `acceptance.md`. The named tests import the real implementation and assert the declared results. The complete runnable fixture is [examples/counted](../examples/counted):

```json
{
  "schema_version": 3,
  "task_id": "addition",
  "root": "..",
  "kind": "task",
  "mode": "light",
  "final_gate": "final",
  "obligations": [
    {
      "id": "R1",
      "text": "Integer addition preserves the selected positive and negative cases",
      "gate": "final",
      "check": "addition-tests"
    },
    {
      "id": "R2",
      "text": "List addition returns combined values without mutating its operands",
      "gate": "final",
      "check": "addition-tests"
    }
  ],
  "gates": [
    {
      "id": "final",
      "level": "task",
      "inputs": [
        "app.py",
        "tests"
      ],
      "criteria": [
        "acceptance.md"
      ],
      "checks": [
        {
          "id": "addition-tests",
          "type": "command",
          "purpose": "behavior",
          "method": "example",
          "scope": "Selected integer addition and operand-preservation regressions",
          "effect": "isolated_test",
          "argv": [
            "python3",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v"
          ],
          "expect_exit": 0,
          "runner": "unittest",
          "min_tests": 2,
          "required_tests": [
            "test_math.MathTests.test_add",
            "test_math.MathTests.test_preserves_inputs"
          ]
        }
      ]
    }
  ]
}
```

The fixture places this at `.proof-of-done/contract.json` with `root: ..`. For `.proof-of-done/addition/contract.json` in another project, use `root: ../..`. Create the criteria and tests with meaningful assertions, then run `lock` before editing product behavior. At delivery, run `finish`; if milestone proofs are current, `finish --reuse` can reuse them. Use fresh `finish` for commands that observe mutable external state outside the input inventory. These optional fields extend this schema-3 engine; an older engine rejects them rather than silently ignoring them.

## Verify that critical checks can reject the violation

For a critical rule whose test sensitivity is uncertain:

1. Establish a passing baseline against the intended implementation.
2. Copy the relevant project into a disposable fixture outside real projects and protected inputs. Preserve the original source and law/acceptance.
3. Introduce one targeted violation, keeping the expected outcome unchanged. For example, remove the guest rejection while retaining an allowed-admin case.
4. Run the related assertion and require failure attributable to that violation. Missing tools, import failures, syntax errors, timeouts and unrelated failing tests leave the control unverified.
5. Retain the control as a durable test when it covers a meaningful gap. Report the observed rejection and its scope alongside the passing implementation evidence.

Select controls proportionally. A small local change may need only its regression. Cross-boundary work should exercise relevant failure paths. Strict work requires a meaningful negative check; targeted mutation helps when a green test might otherwise miss the critical predicate. This is not a requirement to mutate every line or run a mutation suite after each edit.

## Properties and sequences

Use generated or bounded state tests for a real combination or sequencing risk. State the generator domain or exploration bound, retain a deterministic seed and minimized counterexample when available, and reuse the project's existing harness. Examples for a verification engine include verify → change input → finalize, verify → extend obligations → finalize, or interrupt → retry → finalize. Assert the expected decision and persisted state, not only the absence of exceptions.

A finite exhaustive exploration covers its declared domain. Random/generated sampling covers the executed cases. A separate model is evidence about that model; compare it against actual implementation transitions and record the limits. A matching sample is not a universal correspondence proof.

## Describe the strength of evidence

Non-HTTP checks may declare a `method` from `example`, `property`, `bounded`, `model` or `formal`, and a textual `scope`. Scope is mandatory for `bounded`, `model` and `formal`: record domain/bound, subject, premises and important exclusions. These are declared classifications, not certificates mechanically established by their labels. On HTTP checks, `method` retains its existing GET/HEAD meaning; HTTP evidence is reported as example observations.

- `example`: specific executed assertions.
- `property`: generated inputs or sequences with recorded exploration conditions.
- `bounded`: exhaustive coverage of a stated finite domain or bound.
- `model`: evidence concerning a separate model, with its correspondence limits.
- `formal`: a real proof checker accepted a specified statement for an identified artifact, under stated assumptions.

For formal evidence, protect the expected law inventory, identify the checker and dependencies, include the proof and actual code or explicit model in the inputs, and require the real verifier to run. A checker that accepts no laws, a true but irrelevant statement, or a proof of a model unrelated to the product does not establish the user's requirement. Bend's `--check-only` and the second-kernel `--verdict` are distinct evidence. Missing formal infrastructure leaves that obligation pending. Bend is optional; ordinary work needs no new language dependency.

The final comparison should name rules/flows checked, actual execution and any limits. `VERIFIED_SUCCESS` means this declared contract has current acceptable evidence. Coverage percentages describe declared requirements; obligation counts are reported separately. Neither establishes universal correctness of the product.
