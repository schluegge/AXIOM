# Agent B Adversarial Review Charter

Version: 0.6.0

Agent B is a separate deterministic review process, not a second model
instance. It blocks release on any failed check.

Required structured-mutation checks:

- assignment target remains a nested expression AST/HIR
- formatter reparses structured targets
- root mutability and every stable diagnostic are enforced
- field, array, dynamic, nested, and copy-isolation programs match natively
- dynamic write OOB identity/code matches interpreter and native execution
- RHS failure precedes l-value bounds failure
- dynamic index expression executes exactly once
- LLVM bounds guard precedes dynamic GEP and store
- field and nested writes use direct leaf stores
- symbols/effects/ownership expose write facts
- generated valid/OOB write matrix passes
- mutation compiler artifacts are deterministic
- all aggregate/layout/C-ABI and arithmetic/control-flow regressions remain green

A failing assertion may only be changed when evidence proves that the assertion
itself is invalid. The replacement must continue detecting the original defect
class.
