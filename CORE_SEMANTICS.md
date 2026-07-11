# AXIOM Core Semantics

Version: 0.7.0  
Status: existing behavior documented for M0; no language change  
Proven target for native execution: `x86_64-unknown-linux-gnu`

## Scope

This document records the already implemented core shared by the later
arithmetic, aggregate, mutation, and reference extensions. It is normative only
for the v0.7 executable semantic-oracle subset.

## Source and profiles

- source input is UTF-8;
- source positions include byte, line, and column information;
- `profile system;` and `profile script;` are accepted profile declarations in
  the current subset;
- line comments and nested block comments are lexical trivia;
- accepted source has one canonical formatter output.

## Functions

A function declaration has a name, typed parameters, an explicit return type,
and a block body.

```axiom
fn add(left: i32, right: i32) -> i32 {
    return left + right;
}
```

Current laws:

- functions may call previously or subsequently declared functions;
- direct recursion is supported;
- duplicate function names are rejected;
- parameters are immutable bindings;
- argument evaluation is left to right;
- argument count and types must match the declared signature;
- every reachable function path must satisfy the current explicit-return rules;
- `main` is the native/interpreter entry point used by the proof corpus.

## Bindings and lexical scope

```axiom
let immutable: i32 = 1;
var mutable: i32 = 2;
```

- every binding requires an initializer;
- `let` bindings are immutable;
- `var` bindings are mutable;
- local scopes are lexical blocks;
- block-local declarations do not escape;
- redeclaring a still-visible local name is rejected;
- an enclosing `var` may be updated from a nested block;
- parameters remain immutable even inside nested blocks.

Structured assignment and reference-specific restrictions are defined in
`MUTATION_SEMANTICS.md` and `REFERENCE_SEMANTICS.md`.

## Control flow

The current subset provides:

```text
if / else
while
return
```

- conditions have type `bool`;
- `if` and `while` evaluation is deterministic;
- `while` re-evaluates its condition before each iteration;
- the interpreter enforces a deterministic execution-step limit for runaway
  programs;
- the CFG document represents branch, loop-back, and return edges explicitly.

## Primitive values

The v0.7 core primitive types are:

```text
i32
bool
```

Boolean literals are `true` and `false`. Numeric behavior is further restricted
by `ARITHMETIC_SEMANTICS.md`.

## Evaluation and diagnostics

- expression and call-argument order is left to right unless a more specific
  existing semantic document states an additional ordering law;
- dynamic index expressions execute exactly once where indexing is supported;
- diagnostics have stable codes, severity, source span, message, and compiler
  stage;
- invalid input is not silently repaired for later compiler stages;
- the canonical formatter must preserve program structure under
  parse/format/parse comparison.

## Executable documents

For valid programs the current compiler path can emit deterministic documents
for tokens, AST, formatted source, symbols, types, effects, ownership facts,
HIR, CFG, interpreter outcome, LLVM IR, and differential execution.

These documents describe the current compiler result. They do not extend the
source-language semantics by themselves.

## Explicit non-goals in v0.7

This core document does not add or claim:

- strings as a usable source-language data type;
- dynamic allocation or owned resources;
- modules or packages;
- exceptions, null, algebraic variants, `Option`, or `Result`;
- generics;
- external I/O capabilities;
- raw pointers or user-visible `unsafe`;
- concurrency, networking, GPU, embedded, or self-hosting support.
