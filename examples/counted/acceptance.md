# Addition delivery

The same add function must return 3 for add(1, 2), preserve negative-number addition, and concatenate list operands without modifying either input. The selected mandatory cases are test_math.MathTests.test_add and test_math.MathTests.test_preserves_inputs. Both must execute and pass; neither may be ignored or absent. This is example-based evidence about these cases, not a universal proof of addition.

Impact map: add entry point → integer addition and preserved list operands → both mandatory unittest cases in the final gate. Tests, app and acceptance belong to one delivery contract, not contracts per edit. No external state is observed.
