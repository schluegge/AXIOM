# Roadmap Amendment 002 — Mutable Control Flow and Dual Review

## Trigger

The vertical compiler path was proven once. The next work needed to deepen the
language rather than add more shallow targets. The user also requested a second
subagent instance.

## Capability decision

Implement the next visible language capability:

```text
explicit mutable local variables + assignments + while loops
```

This exercises state changes and cyclic control flow across every compiler
stage rather than adding a disconnected feature.

## Review decision

A true second language-model instance cannot be spawned by the available chat
tools. The release process therefore adds:

- an Agent A implementer role
- a separate Agent B review process
- a review-only charter
- independent adversarial fixtures
- an Agent B non-zero blocking exit code
- separate JSON and Markdown review reports

This is recorded as a deterministic reviewer, not misrepresented as a second
AI model.

## Semantic decisions

- `let` is immutable.
- `var` is mutable.
- every binding still requires an initializer.
- parameters are immutable.
- nested blocks may mutate an enclosing `var`.
- declarations inside a nested block do not escape.
- assignment types must exactly match in the current narrow type system.
- `while` conditions must be `bool`.
- the interpreter limits execution steps.
- LLVM stack slots are allocated in the entry block.
- loads/stores model mutable scalar state without PHI nodes.

## New stable diagnostics

```text
AX-MUT-0001
AX-TYPE-0011
AX-TYPE-0012
```

## Result

- Agent A: 15/15 tests passed
- Agent B: 12/12 checks passed
- interpreter loop result: 55
- native loop result: 55
- Evidence layers: 32/32 passed

## Next direction

Specify and implement exact i32 arithmetic semantics before widening the type
system. In particular:

- checked overflow behavior
- division by zero
- signed division overflow (`INT_MIN / -1`)
- interpreter/native equivalence for every boundary case
