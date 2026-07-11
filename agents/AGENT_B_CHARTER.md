# Agent B Adversarial Review Charter

Version: 0.5.0

Agent B is a separate deterministic review process, not a second model
instance. It blocks release on any failed check.

Required aggregate checks:

- AST contains declarations, literals, fields, arrays, and indices
- all stable invalid diagnostics are emitted
- aggregate interpreter/native differential programs pass
- positive and negative runtime bounds failures match identity/code
- generated valid and OOB matrices pass
- LLVM aggregate operations and guard order are present
- every function places required `alloca` operations before its own first branch
- compiler artifacts are deterministic
- Axiom, C, and LLVM layout values agree
- C can consume and return Axiom-compatible simple structs by value
- every v0.4 arithmetic/control-flow regression remains green

A failing assertion may only be corrected when evidence proves the assertion
itself is invalid. The corrected assertion must continue to detect the original
class of implementation defect.
