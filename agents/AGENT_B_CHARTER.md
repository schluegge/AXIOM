# Agent B Adversarial Review Charter

Version: 0.7.0

Agent B is a separate deterministic review process, not a second model
instance. It blocks release on any failed check.

Required reference checks:

- reference AST/types and formatter roundtrip
- shared/mutable interpreter-native parity
- field and array subobject borrows
- non-null pointer lowering without `inttoptr`, `ptrtoint`, or null
- stable conflict and escape diagnostics
- borrow release at block and call-expression boundaries
- left-to-right argument evaluation
- mutable-reference loan linearity over complete argument lists
- nested inner-call loan release and outer-loan retention
- dynamic borrowed index evaluated exactly once
- bounds guard before GEP and dereference
- ownership/symbol/effect borrow facts
- generated reference matrix
- deterministic compiler artifacts
- all v0.6 and earlier regressions remain green

A failing assertion may only be changed when evidence proves that the assertion
itself is invalid. The replacement must continue detecting the original defect
class.
