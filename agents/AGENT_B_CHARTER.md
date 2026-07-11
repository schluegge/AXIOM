# Agent B — Adversarial Reviewer Charter

Role: independent deterministic reviewer  
Version: 0.4.0

This environment cannot spawn a second independent language-model instance.
Agent B is a separate clean Python process with a review-only contract. It
receives the completed repository, runs adversarial checks, and may block the
evidence gate. It does not edit implementation files.

## Required review behavior

- start from repository files, not Agent A's conclusions
- run in a separate process
- use temporary output directories
- report each check independently
- exit non-zero when any check fails
- emit JSON and Markdown reports
- preserve exact exception messages and failing checks

## Required arithmetic attacks

- reject an out-of-range `i32` literal
- overflow checked addition, subtraction, and multiplication
- divide and take remainder by zero
- execute `INT_MIN / -1` and `INT_MIN % -1`
- verify division rounds toward zero
- verify remainder has the dividend sign
- compare interpreter/native panic identity and exit code
- inspect LLVM IR for overflow intrinsics and explicit guards
- confirm arithmetic exposes the `panic` effect

## Regression attacks

- immutable assignment
- assignment type mismatch
- non-boolean while condition
- block-scope escape
- nested mutation
- finite and infinite loops
- entry-block stack allocation
- CFG shape
- deterministic stage outputs
