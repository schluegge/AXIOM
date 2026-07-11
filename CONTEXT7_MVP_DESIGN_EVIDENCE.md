# Context7 MVP Design Evidence

Status: roadmap source evidence  
Scope: design lessons and small helper candidates for the AXIOM MVP  
Not executable proof: Context7 supplies source evidence; repository tools and
benchmarks must produce executable evidence.

## 1. Method

The roadmap did not assume that a new language should invent its own syntax,
compiler components, build system, documentation stack, or benchmark runner.

Context7 was used to inspect official or high-reputation documentation for:

- Rust;
- Zig;
- Go;
- Hyperfine;
- JSON Schema validation;
- Lychee;
- mdBook;
- Tree-sitter.

The resulting decisions distinguish:

- principles adopted into AXIOM semantics;
- established components reused as helpers;
- components deliberately deferred because they do not solve the current
  blocker.

## 2. Rust evidence

Resolved source:

```text
/rust-lang/reference
```

Relevant official contracts observed:

- the Rust Reference is the primary language reference and is distinct from
  introductory material and standard-library documentation;
- language tools and documentation are released with language releases;
- shared and mutable references have distinct access rules;
- `?` has a specified control-flow desugaring rather than being an informal
  convenience;
- Rust combines established ideas, including algebraic data types and pattern
  matching from ML-family languages and move/resource concepts from C++.

AXIOM decisions:

- keep normative language semantics separate from tutorials and standard-library
  API documentation;
- version language, compiler protocol, standard library, and documentation
  together;
- retain distinct shared and mutable references;
- require one documented desugaring for `try`;
- reuse proven language ideas instead of creating novel equivalents for
  algebraic data, matching, moves, or deterministic destruction;
- keep user-visible `unsafe` outside the first MVP product boundary.

Not adopted blindly:

- AXIOM does not copy Rust's complete trait system, macro system, lifetime
  surface, syntax, or ecosystem in the MVP;
- AXIOM's AI-first benchmark must test whether each chosen restriction helps.

## 3. Zig evidence

Resolved source:

```text
/ziglang/www.ziglang.org
```

Relevant official design material observed:

- Zig describes its goals in terms of robust, optimal, and reusable software;
- examples make allocator dependencies explicit rather than hiding allocation
  ownership in global state;
- error unions and optional values are distinct explicit types;
- compile-time execution is a first-class mechanism;
- intent and edge-case behavior are emphasized as maintainability concerns.

AXIOM decisions:

- represent expected error and absence explicitly;
- avoid hidden global authority and hidden resource ownership;
- separate bytes, optional values, errors, and references at the type level;
- require documented edge-case semantics;
- prefer explicit dependencies and capability boundaries.

Deferred:

- general compile-time execution;
- user-selected allocators;
- broad C-replacement and cross-compilation scope.

Reason for deferral:

These are valuable capabilities but do not need to be simultaneous with the
first safe CLI/data product. The MVP uses a documented bundled allocator and
keeps custom allocator recovery post-MVP unless a real blocker appears.

## 4. Go evidence

Resolved source:

```text
/golang/go
```

Relevant official contracts and standard patterns observed:

- Go is specified as a strongly typed compiled language built from packages;
- compact syntax is designed to remain easy for tooling to analyze;
- the canonical `Reader` and `Writer` interfaces are deliberately small and
  composable;
- optional specialized interfaces extend behavior without expanding every base
  interface;
- ordinary failures are explicit values rather than exception-only control flow.

AXIOM decisions:

- make modules/packages a core project boundary rather than an afterthought;
- keep public interfaces small and machine-indexable;
- avoid broad base abstractions that force unrelated capabilities on every type;
- include one canonical formatter and project CLI in the language distribution;
- use explicit typed failures;
- prefer orthogonal standard-library modules over duplicate convenience APIs.

Not adopted:

- garbage collection as the MVP ownership model;
- implicit interface satisfaction;
- `nil`;
- concurrency as an initial language-defining feature.

## 5. Combined language-origin lesson

The useful common pattern is not that successful languages implemented every
feature early. It is that they established a coherent first problem and made
foundational choices reinforce it:

- Rust made safety and ownership architectural rather than a linter convention;
- Zig made explicit control and toolchain behavior architectural;
- Go made simplicity, packages, formatting, and operational tooling part of the
  language experience.

AXIOM therefore makes its first coherent problem:

```text
AI-generated local CLI and structured-data software
```

The MVP makes AI failure reduction architectural through:

- closed-world symbols and dependencies;
- explicit typed failure;
- exhaustive branching;
- safe ownership;
- explicit external capabilities;
- canonical syntax;
- stable semantic diagnostics;
- compact module interfaces;
- reproducible projects;
- a mandatory external benchmark.

## 6. Small helper decisions

### 6.1 Hyperfine

Resolved source:

```text
/sharkdp/hyperfine
```

Observed capabilities:

- warmup runs;
- fixed or bounded run counts;
- parameter scans;
- setup and cleanup outside timed commands;
- result export and statistical command comparison;
- explicit shell or direct execution.

Classification:

```text
CAPABILITY_PROVIDER
```

Use:

- compiler and generated-program process timing after the benchmark contract is
  frozen.

Boundary:

Hyperfine does not define task fairness, semantic equivalence, hardware policy,
or the AI-first statistical claim.

### 6.2 Python jsonschema

Resolved source:

```text
/python-jsonschema/jsonschema/v4.25.1
```

Observed capabilities:

- validator selection from the schema's `$schema` field;
- complete iteration over validation failures;
- instance and schema paths in validation errors;
- support for versioned JSON Schema validation.

Classification:

```text
CAPABILITY_PROVIDER
```

Immediate use:

- M0 machine-readable project/feature contract validation while the Python
  oracle remains active.

Boundary:

JSON Schema validates document structure. The repository checker must separately
validate cross-file facts such as referenced tests, unique diagnostic ownership,
and target claims.

### 6.3 Lychee

Resolved source:

```text
/lycheeverse/lychee
```

Observed capabilities:

- recursive link checking for Markdown and related formats;
- repository-root `lychee.toml` configuration;
- exclusions for known local or non-network link forms;
- GitHub Action and pre-commit integration.

Classification:

```text
CAPABILITY_PROVIDER_WHEN_NEEDED
```

Use:

- documentation link validation when M0 or later documentation introduces links
  that the custom contract checker should not reimplement.

### 6.4 mdBook

Resolved source:

```text
/rust-lang/mdbook
```

Observed capabilities:

- a `SUMMARY.md` navigation structure;
- inclusion of source files into documentation;
- documentation build and Rust doctest support;
- CI integration.

Classification:

```text
WATCH_ONLY_UNTIL_NAVIGATION_BLOCKER
```

Decision:

Do not introduce mdBook during the roadmap-only PR. Adopt it when the normative
specification becomes difficult to navigate or source inclusion removes actual
document drift.

Boundary:

`mdbook test` does not validate AXIOM code blocks by itself. AXIOM examples still
require the AXIOM compiler.

### 6.5 Tree-sitter

Resolved source:

```text
/tree-sitter/tree-sitter
```

Observed capabilities:

- incremental concrete syntax trees;
- efficient reparsing after edits;
- useful trees despite syntax errors;
- generated parser and node metadata;
- corpus tests including expected error cases.

Classification:

```text
ADAPTER_TARGET_POST_MVP_CORE
```

Decision:

Tree-sitter is not a second semantic parser. It is introduced after the compiler
grammar and formatter stabilize enough to support editor tooling. Its corpus
must be checked against the authoritative compiler parser.

## 7. Per-feature Context7 workflow

For every roadmap milestone:

1. name the external API, format, ABI, or helper that is actually required;
2. resolve the official Context7 source;
3. copy exact contracts, versions, and examples into a feature-specific evidence
   section;
4. record the implementation files and tests that use those contracts;
5. classify the dependency or reference;
6. stop with `BLOCKED_SOURCE_MISSING` when the required source cannot be
   established;
7. do not expand research into unrelated tools while the active blocker is
   already solved.

## 8. Current evidence boundary

This document supports roadmap decisions only. It does not yet select exact Rust
crates for:

- source storage;
- lexer generation;
- parser implementation;
- diagnostic rendering;
- LLVM bindings;
- incremental compilation;
- command-line parsing.

Those selections belong to M2 and M3 source-evidence work. Choosing them now
would create speculative dependency commitments before the bootstrap
architecture issue defines exact requirements.
