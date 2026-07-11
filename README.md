# AXIOM v0.7.0 Reference Compiler

AXIOM is an AI-first systems-language research project. This repository contains
an executed Python/LLVM semantic oracle and the M1 foundation of a
provider-neutral benchmark. It is not yet a production compiler or AXIOM v1.0.

The focused v1 product target is:

```text
safe deterministic local CLI and structured-data tools
```

Canonical state and sequence are defined by `contracts/project.json`,
`MVP_ROADMAP.md`, `AI_FIRST_MVP_CONTRACT.md`, `roadmap/v1.json`, issue #9, and
release gate #25. Normative semantic specifications remain authoritative over
summaries and indexes.

## Current compiler path

```text
UTF-8 source
→ lexer and parser
→ versioned AST and canonical formatter
→ semantic, effect, l-value, and borrow analysis
→ layout, HIR, and CFG
→ interpreter and checked LLVM IR
→ Clang executable
→ interpreter/native differential proof
```

## Proven language subset

<!-- AXIOM-PROJECT-CONTRACT:FEATURES:BEGIN -->
- `core.vertical-pipeline` — UTF-8 source, functions, lexical scopes, canonical formatting, semantic documents, interpreter, LLVM, Clang, and differential execution.
- `language.mutable-control-flow` — explicit `let`/`var`, nested mutation, `if`, and `while`.
- `arithmetic.checked-i32` — checked signed `i32` arithmetic and stable runtime fault identities.
- `data.aggregates-fixed-arrays` — structs, fixed arrays, checked indexing, deterministic x86_64 Linux layout, and simple struct-by-value C ABI proof.
- `mutation.structured-lvalues` — whole-value, field, array-element, and nested structured assignment.
- `memory.scoped-references` — non-null scoped `&T` and `&mut T` with conservative lexical whole-root borrow checking.
<!-- AXIOM-PROJECT-CONTRACT:FEATURES:END -->

The primitive source types are `i32` and `bool`. Supported profiles are
`system` and `script`.

## AXIOM-Bench M1 state

`benchmark.contract-0.1` implements the methodology, preregistration, schemas,
offline validator, contamination and fairness laws, trust boundary, and
adversarial contract checks.

`benchmark.trusted-conformance-0.1` implements repository-controlled reference
and seeded-wrong execution, bounded command arrays, deterministic canonical
bundles, and subprocess-free replay. The runner enforces command and task
timeouts plus output, feedback, invocation, candidate-byte, file, and
changed-line limits. Local model-generated candidates remain blocked pending an
approved isolated backend.

Replay verifies candidate bytes against retained attempt hashes and derives
phase outcomes and failure reasons from command records, stream sizes, limits,
and trace terminal events instead of trusting stored outcome flags. The
repository proof attacks both candidate replacement and command-result
rewriting after the attacker repairs the manifest and internal hash chain.

The repository proof uses a synthetic four-language-key fixture to prove runner
mechanics: reference success, exact seeded-wrong rejection, byte-identical
reference bundles, tamper detection, and replay without a subprocess. This is
not a language comparison or evidence that AXIOM is better for AI development.

## Verification

Requirements are Python 3.11+, Clang with textual LLVM IR support, and the exact
packages in `requirements-proof.txt`.

```bash
python3 -m pip install -r requirements-proof.txt
python3 tools/check_project_contract.py
python3 tools/check_benchmark_contract.py
python3 run_repo_proof.py
```

The canonical command creates:

```text
evidence/AXIOM_REPO_PROOF_EVIDENCE.zip
```

The current proof target includes 103 unit/integration tests, 73 separate Agent
B checks, trusted conformance and replay bundles, 38 interpreter/native cases,
52 invalid fixtures, and deterministic Evidence.

## Ordered path to v1.0

M0 is complete. M1 is active. M2 through M13 remain blocked in strict order:
Rust bootstrap, stable protocol, scalar completion, typed failure, generics,
ownership, dynamic text, modules/projects, capabilities, standard library/JSON,
golden applications and Windows/Linux hardening, then the frozen holdout release
decision. Raw pointers and general-purpose `unsafe` remain post-v1.

## Explicit non-proof boundary

The repository does not yet prove a frozen benchmark suite, equal-spec language
packs, real comparison tasks, frozen toolchains, a sandbox for model output,
live-model execution, any AI-first superiority result, the Rust bootstrap,
strings, modules, external capability enforcement, standard library, Windows
parity, broad ABI stability, networking, concurrency, GPU execution, LSP,
package ecosystem, self-hosting, or universal systems-language completeness.

See `PROOF_STATUS.md` for the exact executed boundary.
