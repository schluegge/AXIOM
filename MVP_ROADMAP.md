# AXIOM MVP Roadmap

Status: proposed canonical roadmap  
Tracking issue: #9  
Supersedes as planning authority: the sequence implied by individual roadmap amendments  
Preserves as historical evidence: `ROADMAP_AMENDMENT_001.md` through `ROADMAP_AMENDMENT_006.md`

## 1. Mission

AXIOM's first product is a deterministic, safe language for local command-line
and structured-data programs that is measurably better for AI-driven
development than the comparison languages under a preregistered benchmark.

The MVP is not a syntax demonstration and is not complete merely because a
compiler can execute examples. It is complete only when an AI agent can create,
repair, inspect, build, test, and evolve non-trivial AXIOM projects with less
failure and less corrective work than the strongest comparison language, while
the generated programs retain competitive safety and runtime behavior.

The first product domain is deliberately narrow:

```text
local deterministic CLI and structured-data tools
```

This domain forces AXIOM to solve the foundations that later domains require:

- explicit data and error modeling
- strings, bytes, slices, and owned collections
- safe resource ownership
- modules and stable public interfaces
- deterministic builds
- file, path, environment, and process capabilities
- compiler diagnostics usable by humans and AI agents
- real multi-file maintenance tasks

It does not require AXIOM to develop networking, concurrency, GPU execution,
kernel support, GUI systems, a public package registry, or broad unsafe memory
access at the same time.

## 2. Definition of the MVP

The MVP must compile and run complete projects that can:

1. receive typed command-line arguments;
2. inspect environment values only when declared;
3. read and write files through declared capabilities;
4. manipulate UTF-8 text and arbitrary bytes without unsafe indexing;
5. parse and emit a documented structured-data format;
6. represent expected absence and failure without null or exceptions;
7. use reusable generic data structures;
8. span multiple deterministic modules with explicit visibility;
9. include executable tests in the project;
10. build reproducibly from a manifest and lockfile;
11. emit stable human-readable and machine-readable diagnostics;
12. build native executables on Windows x86_64 and Linux x86_64;
13. expose enough semantic information for an agent to inspect types, symbols,
    effects, borrows, module dependencies, and layouts without scraping prose;
14. pass the complete semantic oracle and Rust bootstrap differential suite;
15. satisfy the AI-first release gate in `AI_FIRST_MVP_CONTRACT.md`.

### Required golden applications

The release candidate must contain and continuously test at least these programs:

1. **Config validator** — reads a structured file, validates nested values, and
   emits stable diagnostics and exit codes.
2. **Text transformer** — streams or processes UTF-8 text, handles malformed
   input explicitly, and writes deterministic output.
3. **Directory manifest generator** — traverses an allowed directory, hashes or
   records files, and emits sorted structured output.
4. **Structured-data query tool** — reads structured input, filters and maps
   values, and reports typed parse and query failures.
5. **Project migration task** — a multi-module program with a public API change,
   downstream compile errors, tests, and a required agent-generated migration.

These applications are product acceptance fixtures, documentation examples,
benchmark seeds, and regression tests. They may not be replaced by isolated
microbenchmarks.

## 3. Explicit non-goals for the MVP

The following are deferred unless an earlier milestone produces evidence that
one is a hard blocker:

- networking and sockets
- threads, async, actors, atomics, and shared-memory concurrency
- GUI, web, mobile, game-engine, or GPU frameworks
- kernel, driver, bare-metal, or embedded execution
- user-visible raw pointers, pointer arithmetic, or general-purpose `unsafe`
- a public package registry
- third-party remote dependencies in ordinary MVP projects
- macros, hygienic or otherwise
- reflection, runtime code generation, or dynamic loading
- inheritance, classes, exceptions, null, or implicit truthiness
- operator overloading
- function overloading
- implicit numeric conversion
- implicit allocation or hidden I/O in language syntax
- a custom linker, debugger, IDE, or version-control system
- self-hosting

Deferral is not rejection. It prevents a second active language front while the
first product domain is still unproven.

## 4. Language design constitution

Every MVP language decision must obey these laws.

### 4.1 Familiar surface, strict meaning

AXIOM keeps familiar, searchable keywords where they already express the right
concept:

```text
fn let var struct enum match if else while return try test use pub
```

Novel syntax requires measured evidence that familiar syntax causes a concrete
failure. The language must not create new spelling merely to appear original.

### 4.2 One canonical form

The formatter is authoritative. The MVP has:

- one statement terminator policy;
- one import form;
- one generic-argument form;
- one canonical layout;
- no alternate aliases for the same construct;
- deterministic ordering for generated documents and manifests.

The parser may recover for diagnostics, but accepted source has one formatter
normal form.

### 4.3 Explicit state and effects

- `let` is immutable.
- `var` is mutable.
- public function signatures are fully typed.
- mutation is visible at the binding or reference.
- file, environment, and process access are declared effects/capabilities.
- pure functions cannot invoke external effects through hidden call paths.
- global mutable state is forbidden in the MVP.

### 4.4 No ambient absence or failure

- no `null`;
- no exceptions;
- expected absence uses `Option<T>`;
- expected failure uses `Result<T, E>`;
- `match` is exhaustive;
- `try` is explicit propagation syntax with one documented desugaring;
- panic is reserved for violated internal invariants or unrecoverable runtime
  conditions and remains an explicit effect in compiler documents.

### 4.5 Deterministic evaluation

- function arguments evaluate left to right;
- assignment preserves the defined right-hand-side and l-value order;
- dynamic indices execute once;
- destruction order is specified;
- module initialization order is acyclic and specified;
- map/object serialization is deterministic where the standard library claims
  deterministic output.

### 4.6 Safe by default

- integer arithmetic is checked by default;
- wrapping, saturating, and unchecked operations require distinct explicit APIs;
- array and slice indexing is checked;
- references are non-null and non-forgeable;
- owned resources have deterministic destruction;
- use-after-move, double destruction, dangling references, and conflicting
  mutation are rejected;
- UTF-8 strings cannot be indexed as if bytes were characters;
- unsafe user code is outside the MVP.

### 4.7 Closed-world dependency resolution

The compiler resolves only:

- the current project;
- declared workspace modules;
- the exact bundled standard library;
- dependencies recorded in the manifest and lockfile when third-party local
  packages are introduced.

An unknown name or import never triggers an automatic package download. A
compiler hint may reference only symbols that exist in the resolved symbol
index.

### 4.8 Limited inference

Local types may be inferred when the initializer determines one unambiguous
static type. Public signatures, exported constants, aggregate fields, effect
contracts, and generic boundaries remain explicit.

Inference must never perform an implicit numeric conversion, borrow, clone,
allocation, error conversion, or capability acquisition.

### 4.9 No accidental shadowing

The MVP rejects a declaration that shadows a still-live local, parameter,
import, module, type, or public symbol. Reuse of a name is allowed only after the
previous binding's scope has ended. This reduces mistaken edits and ambiguous
agent reasoning.

### 4.10 Diagnostics are a language interface

Every diagnostic has:

- stable code;
- severity;
- primary source span;
- related spans;
- machine-readable cause category;
- actual and expected semantic facts where applicable;
- safe candidate actions derived only from compiler-known facts;
- documentation key;
- schema version.

Diagnostics must not fabricate code, APIs, dependencies, or semantic intent.

## 5. Foundation architecture

### 5.1 Semantic oracle

The current Python/LLVM implementation remains the executable semantic oracle
until the corresponding Rust bootstrap stage passes differential parity and is
explicitly promoted to authority.

The oracle is optimized for semantic clarity, generated fixtures, and rapid
critic loops. It is not the final compiler product.

### 5.2 Rust bootstrap compiler

The production MVP compiler is written in Rust. The bootstrap begins before
additional broad language growth, because postponing it would create a second
full compiler port after the language has already expanded.

The Rust compiler must reuse established components where evidence supports
them. It must not implement a custom linker or object format. LLVM/Clang/LLD or
another existing proven backend path remains the default until a benchmarked
blocker justifies change.

### 5.3 Compiler pipeline

The MVP pipeline remains explicit and inspectable:

```text
source
→ lossless source representation
→ lexer
→ parser / syntax tree
→ versioned semantic AST
→ canonical formatter
→ name resolution
→ type analysis
→ effect/capability analysis
→ place/l-value analysis
→ ownership and borrow analysis
→ target layout
→ HIR
→ CFG
→ interpreter oracle
→ LLVM IR
→ native object/executable
→ differential result
```

A stage may not silently repair invalid input for later stages.

### 5.4 Supported targets

MVP release targets:

```text
x86_64-unknown-linux-gnu
x86_64-pc-windows-msvc
```

Target-specific ABI, layout, runtime, and linker claims must name the target.
macOS, ARM, WebAssembly, embedded, and freestanding targets are deferred.

### 5.5 Distribution

The MVP release contains:

- `axiom` compiler and project CLI;
- bundled standard library source and machine-readable interface index;
- target runtime components;
- license and third-party notices;
- exact compiler build metadata;
- SHA-256 checksums;
- Windows and Linux archives;
- a source archive;
- benchmark protocol and frozen result bundle;
- language reference and getting-started guide.

## 6. Why AI-generated code fails and the corresponding AXIOM response

| Repeated failure | Common external remedy | AXIOM MVP language/toolchain response |
|---|---|---|
| Invented APIs and packages | retrieval, API docs, lockfiles | closed-world symbol index, declared modules, exact std version, no auto-install |
| Missing repository context | larger context windows, repository agents | explicit module graph, compact interface documents, explain queries |
| Code compiles but violates intent | tests, hidden tests, repair loops | exhaustive data modeling, built-in tests, benchmark holdouts, no claim from compile success |
| Insecure defaults | linters, scanners, human review | no null/exceptions, checked arithmetic/indexing, ownership, capabilities, secure APIs |
| Weak handling of errors | retries and prompt instructions | `Result`, `Option`, exhaustive `match`, explicit `try` |
| Stale or copied documentation | retrieval and doc generation | compiled examples, versioned schemas, contract checker |
| Large noisy patches | formatters and AST tools | canonical formatter, stable syntax documents, future structured edit protocol |
| Hidden I/O and authority | sandboxing and policy layers | declared effects and capability-limited standard library |
| Dependency confusion | package scanning and allowlists | no remote registry in MVP, exact manifest/lock resolution |
| Superficial test passing | mutation testing and adversarial suites | Agent B, generated invalid/boundary cases, hidden benchmark tests |
| Feedback fixes syntax but not logic | iterative execution | separate syntax, semantic, repair, and repository benchmarks |
| Benchmark contamination | rolling or private tests | versioned holdouts, post-cutoff tasks, preserved prompts and outputs |

The language does not assume that compiler feedback solves algorithmic errors.
The benchmark measures logical correctness separately.

## 7. Ordered implementation roadmap

Only one milestone is the active language front. A milestone may contain several
internal steps, but they are merged in the listed order and each must remain a
vertically complete capability.

### M0 — Freeze v0.7 and establish project authority

Goal: stop semantic expansion long enough to make the product claim,
measurement contract, and document authority explicit.

Deliverables:

- `MVP_ROADMAP.md` as the canonical roadmap;
- `AI_FIRST_MVP_CONTRACT.md`;
- `ROADMAP_AMENDMENT_007.md` recording the pivot;
- `CONTEXT7_MVP_DESIGN_EVIDENCE.md`;
- one machine-readable project contract and JSON Schema;
- a minimal contract checker;
- explicit document authority and supersession rules;
- tracking issue #9;
- issue #8 marked post-MVP;
- current v0.7 proof rerun unchanged.

The project contract records only facts needed for consistency:

- project and schema version;
- current language version;
- implemented features;
- normative specification file;
- tests and proof stage;
- diagnostics owned by the feature;
- proven targets;
- benchmark IDs;
- status: proposed, implemented, proven, or deferred.

Exit gate:

- no unresolved contradictions among README, AGENTS, proof status, semantics,
  amendments, roadmap, and feature registry;
- every v0.7 feature maps to a normative document and executable evidence;
- current repository proof remains green;
- no new syntax or runtime behavior is introduced.

### M1 — AXIOM-Bench seed and preregistration

Goal: establish a measurement baseline before optimizing the language toward a
model or benchmark.

Deliverables:

- benchmark task schema;
- prompt and language-pack schema;
- result schema;
- fixed-budget runner;
- raw completion and trace archive format;
- v0.7-solvable seed tasks;
- equivalent Rust, Zig, and Go task implementations and hidden tests;
- separate language-only, compiler-assisted, and full-agent lanes;
- contamination metadata and task creation dates;
- benchmark version `0.1` frozen before the next language feature.

Seed task families:

- arithmetic and boundary behavior;
- state and loops;
- aggregate construction and transformation;
- checked indexing;
- structured mutation;
- reference aliasing and borrow rejection;
- compiler-error repair;
- formatter roundtrip;
- small multi-function changes within one file.

This seed is not allowed to support a public claim that AXIOM is generally
better. It validates methodology and provides a before-state.

Exit gate:

- every task runs unattended;
- hidden tests distinguish at least one plausible wrong solution from the
  correct solution;
- all failures are retained;
- benchmark reports language-only and tool-assisted results separately;
- result reproduction succeeds from a clean checkout.

### M2 — Rust bootstrap parity for v0.7

Goal: establish the production compiler architecture before the language grows
substantially beyond the oracle.

Implementation order:

1. isolated Rust workspace and locked dependencies;
2. UTF-8 source loader and source spans;
3. lexer;
4. parser and versioned AST;
5. canonical formatter;
6. name and type analysis;
7. arithmetic and control flow;
8. aggregates and layout;
9. structured mutation;
10. scoped references and borrow rules;
11. HIR and CFG documents;
12. interpreter or oracle-compatibility executor;
13. LLVM lowering and runtime boundary;
14. native differential suite;
15. deterministic Evidence.

Every stage must consume the existing fixtures and compare canonical documents,
diagnostics, interpreter outcomes, LLVM invariants, and native outcomes.

Promotion law:

- Python remains authority for a stage until Rust parity passes;
- authority transfer is recorded per stage;
- after transfer, new feature work modifies Rust first or in the same PR and the
  Python oracle remains an independent differential implementation;
- a green result may not be obtained by making both implementations share the
  same semantic code.

Exit gate:

- all v0.7 valid, invalid, boundary, generated, and Agent B cases pass;
- Rust and Python canonical semantic documents agree;
- Windows and Linux bootstrap compiler smoke tests pass;
- the Rust compiler can produce the same supported native outcomes;
- Evidence identifies toolchain versions and target triples.

### M3 — Stable compiler interaction protocol

Goal: make the compiler a precise interface for humans and agents before adding
new semantic complexity.

Required commands:

```text
axiom check <project-or-file>
axiom check --format json <project-or-file>
axiom format <path>
axiom format --check <path>
axiom run <project> [-- <args>]
axiom build <project>
axiom test <project>
axiom explain symbol <name>
axiom explain type <expression-or-symbol>
axiom explain effect <function>
axiom explain borrow <function-or-span>
axiom explain layout <type>
axiom explain module <module>
```

Protocol documents:

- diagnostics;
- source files and hashes;
- symbols and references;
- types;
- effects;
- ownership and borrow facts;
- HIR and CFG;
- target layouts;
- module graph;
- build plan;
- test results.

All JSON documents receive explicit `document_kind` and `schema_version` fields.
Breaking protocol changes require a schema version change and migration note.

Exit gate:

- every command has stable exit codes;
- text and JSON outputs represent the same semantic result;
- malformed projects still produce valid diagnostic JSON;
- a benchmark A/B run compares text-only and structured feedback;
- no command silently edits files except `format`, and `format --check` is read-only.

### M4 — Scalar completeness and explicit conversion

Goal: support the numeric and byte-level values needed by real data tools
without introducing implicit conversion.

Capabilities, merged one at a time:

1. `u8` for bytes;
2. `usize` for sizes and indices;
3. `i64` and `u64` for practical file and structured-data values;
4. `f64` with documented IEEE-754 behavior;
5. explicit checked conversions;
6. explicit wrapping and saturating arithmetic APIs;
7. canonical parse and format operations.

Rules:

- no implicit widening or narrowing;
- literals must resolve to one type from context or require a suffix;
- integer operations preserve checked defaults;
- float-to-int and int-to-float conversions are explicit and may fail;
- NaN behavior, signed zero, comparison, formatting, and serialization are
  specified;
- indices use `usize`; source-visible conversion from signed values is checked.

Exit gate:

- interpreter/native parity for boundary values;
- cross-target layout documents;
- canonical numeric text roundtrip;
- generated conversion matrix;
- benchmark tasks include wrong-width, overflow, NaN, and index-conversion traps.

### M5 — Algebraic variants, exhaustive matching, and typed failure

Goal: make expected absence and failure explicit before dynamic resources and
I/O are introduced.

Capabilities, merged in order:

1. nominal `enum` variants without payloads;
2. payload variants;
3. exhaustive `match` expressions;
4. pattern bindings;
5. `Option<T>`;
6. `Result<T, E>`;
7. explicit `try` propagation;
8. stable error-context APIs without exceptions.

Rules:

- `match` is exhaustive and has no implicit default arm;
- unreachable or duplicate patterns are diagnostics;
- payload field order and layout are specified per target;
- `try expression` is valid only for compatible `Result` propagation and has one
  documented desugaring;
- error conversion is never implicit;
- `Option<T>` is not represented as a null reference at the source semantic
  level;
- panic remains separate from expected failure.

Exit gate:

- parser through native execution is complete;
- invalid and generated exhaustiveness matrices pass;
- result propagation preserves evaluation order and effects;
- formatter roundtrip covers nested patterns;
- AI benchmark measures omitted cases, wrong error variants, and repair quality.

### M6 — Minimal generics and reusable static abstractions

Goal: support `Option<T>`, `Result<T, E>`, slices, and collections without
copy-pasted type-specific implementations or a broad trait system.

MVP generic surface:

- nominal generic structs and enums;
- generic functions;
- explicit type parameters on public declarations;
- local inference where unique;
- monomorphized code generation;
- a small closed set of compiler-known capabilities required for generic
  operations, initially `Copy`, `Drop`, `Eq`, and `Order` only if the active
  standard-library slice proves each necessary.

Deferred:

- higher-kinded types;
- specialization;
- implicit typeclass search;
- associated types;
- user-defined operator overloading;
- compile-time reflection;
- macros.

Exit gate:

- deterministic instantiation and symbol naming;
- recursive instantiation and cycle limits;
- stable diagnostics for unresolved or ambiguous generic arguments;
- generated monomorphization matrix;
- no semantic dependence on backend-specific template behavior;
- benchmark compares generic API discovery and error repair.

### M7 — Ownership, moves, and deterministic destruction

Goal: establish safe dynamic resource semantics before introducing owned buffers
and strings.

Capabilities, merged in order:

1. move-only values;
2. explicit copy eligibility;
3. moved-value diagnostics;
4. deterministic lexical destruction;
5. partial initialization rules;
6. early-return and panic cleanup;
7. safe borrowing of owned values;
8. non-escaping slice/reference lifetime rules required by M8.

Rules:

- assignment and argument passing state whether a value moves or copies from its
  type capability;
- the compiler never inserts an expensive clone;
- destruction order is reverse declaration order within a scope unless a more
  specific language rule applies;
- double destruction and use-after-move are impossible in valid source;
- resource destruction runs on ordinary return and expected-error propagation;
- panic cleanup semantics are explicit and target-tested;
- self-referential owned values are outside the MVP.

Exit gate:

- ownership facts are present in compiler protocol documents;
- generated control-flow cleanup matrix passes;
- interpreter and native destruction traces agree;
- Agent B includes alias, move, early-return, and nested-scope attacks;
- benchmark measures ownership repair without permitting hidden clones.

### M8 — Owned bytes, slices, UTF-8 strings, and lists

Goal: make real input, output, and data transformation possible using the M7
ownership foundation.

Capabilities, merged in order:

1. immutable and mutable slices;
2. owned byte buffer;
3. owned generic list;
4. UTF-8 string;
5. string and byte views;
6. iteration over bytes and Unicode scalar values;
7. safe slicing at documented boundaries;
8. deterministic builders and formatting.

Rules:

- bytes and text are distinct types;
- string indexing by integer is forbidden;
- byte slicing and text slicing have separate APIs;
- text APIs either preserve UTF-8 validity or return typed errors;
- allocation never occurs through an operator whose spelling does not indicate a
  collection/string operation;
- the MVP uses the bundled runtime allocator and treats allocator exhaustion as
  an explicit documented unrecoverable runtime condition; custom allocators are
  post-MVP unless evidence makes recovery a blocker;
- collection growth behavior is documented but not part of source semantics
  unless observable.

Exit gate:

- malformed UTF-8 corpus;
- bounds and boundary corpus;
- move/borrow/destruction matrix;
- deterministic formatter and serialization helpers;
- Windows/Linux file-content parity;
- benchmark includes byte/text confusion, Unicode boundaries, and stale-slice
  errors.

### M9 — Modules, visibility, projects, manifest, and lockfile

Goal: move from isolated programs to maintainable repositories.

Module rules:

- one canonical mapping from source paths to module names;
- explicit `use` imports;
- imports are module-qualified by default;
- `pub` is required for exported declarations;
- private is default;
- wildcard imports are forbidden in the MVP;
- cyclic module initialization is forbidden;
- type-only dependency cycles are either precisely supported or rejected; no
  accidental backend behavior;
- public signatures cannot expose inaccessible private types.

Project rules:

- one manifest format;
- one lockfile format;
- exact language edition and compiler compatibility declaration;
- explicit target and profile settings;
- workspace-local dependencies first;
- no public remote registry in the MVP;
- hashes and canonical paths in the lockfile;
- deterministic module and build graph;
- undeclared files cannot affect a build except documented project metadata.

Exit gate:

- multi-module valid, invalid, and migration fixtures;
- deterministic clean and incremental build plans;
- module interface documents small enough for agent retrieval;
- unknown-import diagnostics suggest only resolved modules;
- benchmark includes multi-file API changes and stale import repair.

### M10 — External-effect and capability model

Goal: prevent hidden authority while keeping ordinary CLI code understandable.

MVP capability families:

```text
env.args
env.read
fs.read
fs.write
fs.list
process.stdout
process.stderr
process.exit
clock.monotonic
```

Wall-clock time, randomness, networking, subprocess creation, and unrestricted
filesystem authority are deferred unless a golden application proves them
necessary.

Rules:

- pure is the default;
- public functions declare external effects;
- private functions may have effects inferred, but the compiler validates them
  against the nearest public boundary and exposes them through `explain effect`;
- project manifests grant entry-point capabilities;
- a program cannot call an API requiring an ungranted capability;
- path access is mediated through the granted filesystem capability;
- standard-library APIs document deterministic and nondeterministic behavior;
- tests receive explicit test capabilities and isolated temporary roots.

Exit gate:

- effect propagation and rejection matrix;
- no hidden environment or filesystem reads in the standard library;
- capability grants appear in build plans and Evidence;
- golden applications run with least required capability sets;
- benchmark includes overbroad-authority and missing-capability repairs.

### M11 — Minimal standard library and structured data

Goal: complete the first product domain without creating a broad ecosystem.

Required modules:

```text
std.option
std.result
std.bytes
std.text
std.list
std.iter
std.format
std.cli
std.env
std.path
std.fs
std.io
std.json
std.test
```

The structured-data commitment for the MVP is JSON because it exercises nested
variants, strings, numbers, arrays, objects, parsing failures, deterministic
serialization, files, and common AI-generated integration tasks.

JSON rules:

- complete documented JSON grammar;
- UTF-8 validation;
- explicit integer and floating-number representation policy;
- duplicate object-key policy;
- configurable or fixed resource limits documented;
- stable parse errors with spans;
- deterministic object serialization policy;
- parser and serializer implemented as ordinary AXIOM/library code where
  practical, with runtime intrinsics limited and documented.

Standard-library policy:

- small orthogonal APIs;
- no duplicate convenience aliases;
- no hidden global state;
- every public API in the machine-readable symbol index;
- examples compile in CI;
- behavior and error variants specified;
- no API is added solely because another language has it.

Exit gate:

- all five golden applications can be implemented without user-visible C code;
- standard-library examples and tests pass on Windows/Linux;
- API surface audit finds no undocumented public symbol;
- benchmark language packs are generated from the exact released interface.

### M12 — Golden applications, cross-platform release, and hardening

Goal: prove that the language is a product rather than a collection of
features.

Required work:

- implement the five golden applications in AXIOM;
- equivalent Rust, Zig, and Go versions under the same behavioral contract;
- end-to-end install/build/test/run on clean Windows and Linux runners;
- deterministic project archives;
- release artifact checksums;
- compiler crash corpus;
- fuzz/property tests where they address observed parser, formatter, or semantic
  failures;
- memory and undefined-behavior checking of compiler/runtime with established
  tools where supported;
- cold and warm compile benchmarks;
- native runtime benchmarks;
- binary-size and peak-memory measurements;
- documentation walkthrough from a clean machine.

Performance is not allowed to redefine semantics. Optimizations must preserve
oracle and bootstrap differential behavior.

Exit gate:

- all golden applications pass hidden acceptance tests;
- clean install and build work on both targets;
- no known critical compiler crash on the release corpus;
- no unclassified unsafe block in compiler/runtime code;
- all release documents state exact proof and non-proof boundaries.

### M13 — Frozen holdout benchmark and MVP release decision

Goal: test the AI-first claim without changing the language or benchmark after
seeing holdout results.

Procedure:

1. tag the release candidate;
2. freeze compiler binaries, standard library, language packs, prompts, model
   versions, tool permissions, budgets, and hardware contract;
3. reveal or generate the holdout set through the preregistered process;
4. run at least two independent model families;
5. preserve every completion, failure, repair, command, output, token count, and
   timing result;
6. calculate confidence intervals and primary endpoints;
7. publish positive and negative findings;
8. decide one of three outcomes.

Possible outcomes:

- **MVP_PASS** — all correctness and AI-first hard gates pass;
- **MVP_LANGUAGE_VALID_TOOLING_INSUFFICIENT** — language-only results pass but
  compiler/agent workflow gates fail;
- **MVP_AI_FIRST_NOT_PROVEN** — the product may be technically usable, but the
  AI-first superiority claim is not permitted.

Failure does not authorize benchmark rewriting. It creates the next design issue
from observed error classes.

## 8. Development workflow for every capability

### Step 1 — Problem statement

The issue names:

- the real program currently blocked;
- the exact AI failure class targeted;
- the comparison-language behavior;
- the falsifiable expected improvement;
- explicit non-goals.

### Step 2 — Source evidence

Before using an external compiler API, ABI rule, runtime function, library, file
format, operating-system contract, or benchmark tool:

- resolve official documentation through Context7 when available;
- capture exact contracts and versions;
- classify the external component as `CAPABILITY_PROVIDER`, `ADAPTER_TARGET`,
  `REFERENCE_ONLY`, `WATCH_ONLY`, `REJECT`, or another repository-approved
  category;
- stop with `BLOCKED_SOURCE_MISSING` when required evidence is absent.

### Step 3 — Normative semantics

The specification is updated before implementation and defines:

- grammar;
- typing;
- name resolution;
- evaluation order;
- effects;
- ownership/borrowing;
- runtime behavior;
- layout/ABI scope;
- diagnostics;
- formatter behavior;
- explicit non-goals.

### Step 4 — Vertical implementation

A normal feature is incomplete until all affected stages agree:

```text
lexer → parser → AST → formatter → semantic analysis → protocol documents
→ HIR/CFG → interpreter → LLVM/native → CLI → tests → documentation
```

After M2, Rust bootstrap parity is part of the same release gate.

### Step 5 — Proof matrix

Required test categories:

- valid examples;
- invalid examples for every diagnostic branch;
- boundary values;
- adversarial alias/effect/ownership/control-flow cases;
- generated combinations;
- formatter parse/format/parse equivalence;
- interpreter/native differential behavior;
- Python/Rust oracle parity while both exist;
- previous-version regressions;
- Windows/Linux target cases where relevant.

### Step 6 — Benchmark delta

Every feature adds benchmark tasks that can disprove its AI-development
hypothesis. Historical benchmark versions remain immutable.

A feature is not automatically rejected for a negative AI result, but the
result must be recorded and the feature must still justify its product value.

### Step 7 — Independent review

Agent B remains deterministic and release-blocking. Its charter expands to check:

- semantic contradictions;
- weakened critic assertions;
- hidden implicit behavior;
- benchmark leakage or gaming;
- undocumented public APIs;
- mismatch between human and JSON diagnostics;
- target claims without target evidence;
- accidental second active language front.

### Step 8 — Exact-PR Evidence

The exact pull-request head must produce:

- proof manifest;
- tool versions;
- test and review reports;
- benchmark smoke results;
- generated protocol documents;
- cross-target results where applicable;
- deterministic Evidence archive;
- known-unproven list.

## 9. Repository and document authority

The authority order is:

1. normative semantic specifications;
2. machine-readable feature/project contract for indexing those specifications;
3. this roadmap for sequence and scope;
4. release gates and benchmark contract;
5. amendments/ADRs for historical rationale;
6. README as a generated or checked summary.

An amendment may change the roadmap only by explicitly editing the canonical
roadmap and explaining the change. Amendments no longer form an implicit future
sequence by themselves.

The document checker must validate:

- referenced files exist;
- versions agree;
- diagnostics are unique;
- implemented features have specifications and tests;
- proven targets are named;
- examples compile or produce the expected diagnostic;
- benchmark IDs exist;
- README claims do not exceed the feature registry;
- deferred work is not presented as implemented;
- historical documents do not override current authority.

## 10. Benchmark and performance lanes

Results are never collapsed into one unexplained score.

### Language design lane

Measures source generation using equal-size, task-limited language packs and no
AXIOM-specific agent tools.

### Compiler interaction lane

Measures the value of structured diagnostics and explain documents against plain
text compiler feedback.

### Full agent lane

Measures repository navigation, editing, build, test, and repair with identical
tool budgets.

### Compiler implementation lane

Measures frontend and complete build time, peak memory, incremental behavior,
and binary distribution size.

### Generated program lane

Measures runtime, peak memory, binary size, deterministic output, and safety
checks of equivalent programs.

The MVP claim concerns AI-driven task success, not winning every runtime or
compiler-speed benchmark. Runtime and compiler regressions remain visible and
bounded by release policy.

## 11. Tool reuse policy

AXIOM is a language project, not a reimplementation contest.

Default decisions:

- reuse Rust and Cargo for the bootstrap compiler build;
- reuse LLVM/Clang/LLD for native backend work unless blocked;
- reuse JSON Schema validation for machine-readable contracts;
- reuse established statistical process benchmark tools;
- reuse link checking and documentation tooling when documentation volume makes
  them necessary;
- use Tree-sitter later as an editor adapter, never as semantic authority;
- use C ABI only through documented, target-specific boundaries;
- do not build a package registry, IDE, linker, debugger, or test framework when
  an established component satisfies the current contract.

A dependency must earn inclusion by reducing a current blocker more than it
adds supply-chain, portability, determinism, or maintenance risk.

## 12. Risk register

### Benchmark overfitting

Mitigation: frozen preregistration, holdouts, multiple model families, immutable
historical results, and no syntax change justified by one model alone.

### Training-data disadvantage

Mitigation: publish both natural-knowledge and equal-spec lanes. The hard MVP
claim uses equal-spec conditions.

### Training-data contamination

Mitigation: timestamped task provenance, new holdouts, preserved prompts, and
post-release benchmark additions rather than silent replacement.

### Oracle/bootstrap agreement by shared bug

Mitigation: independent implementations, generated adversarial cases, native
execution, and comparison-language reference programs.

### Governance replacing product work

Mitigation: only M0 introduces governance infrastructure. Later governance work
must remove a demonstrated blocker.

### Language breadth explosion

Mitigation: one active language front and explicit MVP non-goals.

### Rust-port stagnation

Mitigation: bootstrap parity occurs at M2 before additional broad feature growth.

### Standard-library explosion

Mitigation: only APIs required by golden applications enter the MVP.

### Unsafe runtime hidden beneath safe syntax

Mitigation: inventory every compiler/runtime unsafe block, document invariants,
and run available memory/UB tooling on release targets.

### Pleasant syntax hiding ambiguous semantics

Mitigation: familiar syntax is accepted only with one canonical desugaring and
machine-readable semantic output.

### AI-first claim reduced to diagnostics

Mitigation: language-only, compiler-assisted, and full-agent benchmark lanes
remain separate.

## 13. MVP release checklist

The release is not called complete until all entries are true:

- [ ] canonical roadmap and AI-first contract are current;
- [ ] v0.7 historical evidence remains reproducible;
- [ ] Rust bootstrap owns the complete MVP compiler path;
- [ ] Python oracle remains a valid independent differential oracle or is
      explicitly retired by a proven replacement plan;
- [ ] all required language features and non-goals are documented;
- [ ] compiler protocol schemas are versioned and validated;
- [ ] Windows and Linux release targets pass;
- [ ] formatter output is canonical;
- [ ] module/project builds are reproducible;
- [ ] standard library public APIs are fully indexed and documented;
- [ ] five golden applications pass public and hidden tests;
- [ ] all documentation examples are executable;
- [ ] complete proof and Agent B review pass;
- [ ] benchmark preregistration predates holdout execution;
- [ ] raw benchmark artifacts are published;
- [ ] AI-first hard gates pass or the claim is explicitly withheld;
- [ ] known limitations and unproven boundaries are included in the release.

## 14. Immediate next implementation action

After this roadmap PR is reviewed, the next and only active implementation task
is M0:

```text
create the minimal machine-readable project contract, its JSON Schema, and a
checker that proves the existing v0.7 documents and tests agree without changing
language semantics
```

No raw-pointer work, new syntax, package system, LSP, or standard-library growth
starts before M0 and the M1 benchmark seed are complete.
