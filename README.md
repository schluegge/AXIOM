# AXIOM v0.7.0 Reference Compiler

AXIOM is an AI-first systems-language research project. This repository contains
an executed Python/LLVM semantic oracle and the M1 foundation of a
provider-neutral benchmark. It is not yet a production compiler or AXIOM v1.0.

The focused v1 product target is:

```text
safe deterministic local CLI and structured-data tools
```

Normative semantic and benchmark specifications are the primary authority.
`contracts/project.json` is the validated current-state index;
`MVP_ROADMAP.md` and `roadmap/v1.json` govern implementation sequence;
`AI_FIRST_MVP_CONTRACT.md` governs measurable release claims. GitHub issues #9
and #25 track the program and release gate but do not override repository
contracts.

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

`benchmark.trusted-conformance-0.1` implements trusted reference and seeded-wrong
execution through the public `axiom_bench` package and repository CLI tools.
Before output creation or process execution, those entry points require the
exact task path to appear in
`benchmarks/contracts/0.1.0/trusted-tasks.json`. The registry, its schema, the
task schema, the repository-relative path, symlink boundary, and task ID are
validated together. Unregistered task paths fail with
`AX-BENCH-RUNNER-UNTRUSTED-TASK`.

The runner uses bounded command arrays and deterministic canonical bundles. It
enforces command and task timeouts plus output, feedback, invocation,
candidate-byte, file, and changed-line limits. Local model-generated candidates
remain blocked pending an approved isolated backend.

Canonical command records and stdout/stderr payloads replace temporary workspace
and task-root paths with stable placeholders. Raw Evidence retains the original
bytes outside the canonical bundle. Replay bounds actual decompressed ZIP bytes,
not only archive metadata, and converts malformed or memory-exhausting input
into a failed report.

Replay first verifies internal paths, bytes, hashes, commands, outcomes, limits,
and trace events without starting a subprocess. A passing internal replay is
then checked against repository authority: the registered task ID and task
SHA-256, selected language variant, adapter-derived trust class, and the expected
reference or seeded-wrong outcome. The expected outcome is not accepted from the
bundle as its own authority. A disagreement fails with
`AX-BENCH-REPLAY-AUTHORITY`.

The repository proof attacks candidate replacement, command-result rewriting,
external copied tasks, registered-task hash replacement, and coherent
seeded-wrong-to-reference relabeling after the attacker repairs the manifest and
internal hash chain.

The repository proof uses a synthetic four-language-key fixture to prove runner
mechanics: reference success, exact seeded-wrong rejection, byte-identical
reference bundles, authority enforcement, tamper detection, and replay without
a subprocess. This is not a language comparison or evidence that AXIOM is better
for AI development.

`axiom_bench.runner` and `axiom_bench.replay` contain implementation helpers.
The supported authority-enforcing interfaces are the exports from
`axiom_bench`, the repository CLI tools, and `run_repo_proof.py`.

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

The current proof target includes 179 unit/integration tests, 99 separate Agent
B checks, trusted conformance and authority-bound replay bundles, 38
interpreter/native cases, 52 invalid fixtures, and deterministic Evidence.

## Automated review state

`review.report-contract-0.1` implements the versioned automated-review report
contract with offline validation and safe deterministic rendering.
`review.deterministic-gate-0.1` implements the deterministic pull-request
review gate: one offline command that recomputes the repository contracts,
verifies exact-head proof evidence, enforces a versioned protected baseline,
rejects unpinned actions, `pull_request_target` triggers, and widened workflow
permissions, and fails closed.

`review.safe-publisher-0.1` adds the privileged half of the two-stage boundary.
The read-only PR workflow uploads a digest-bound publication envelope while the
separate default-branch `workflow_run` publisher validates the raw ZIP without
extraction, checks repository/PR/run/head identity and trusted rendering, and
creates or updates one bounded marker comment. Older or stale runs cannot
overwrite a newer current publication. The publisher never checks out or
executes pull-request code and has no approval, merge, auto-merge, label, or
branch-policy authority. AI review remains advisory-only by contract and is not
implemented.

```bash
python3 run_repo_proof.py
python3 tools/run_deterministic_review.py --pull-request <n> \
  --base-sha "$(git merge-base origin/main HEAD)"
```

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