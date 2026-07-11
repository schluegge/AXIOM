## Owning work item

Closes #
Parent milestone: #
Target release: AXIOM v1.0

## Real blocker and visible capability

Describe the concrete program/workflow blocker removed by this PR and the one vertically complete capability delivered.

## AI-development hypothesis

State the falsifiable failure-reduction hypothesis and the benchmark task(s) that can disprove it.

## Source evidence

- [ ] External APIs, ABI rules, runtime contracts, file formats, and tools were sourced from official documentation before implementation.
- [ ] Exact versions/signatures/configuration are recorded in repository evidence.
- [ ] No required contract is missing; otherwise this PR is marked `BLOCKED_SOURCE_MISSING`.

## Normative semantics and scope

List updated grammar, typing, names, evaluation order, effects, ownership/borrowing, runtime behavior, diagnostics, formatter behavior, target boundaries, and explicit non-goals.

## Vertical implementation

- [ ] lexer/source representation
- [ ] parser and versioned AST
- [ ] canonical formatter
- [ ] semantic/type/effect/ownership analysis
- [ ] protocol documents
- [ ] HIR/CFG
- [ ] Python oracle where still required
- [ ] Rust bootstrap parity where required
- [ ] interpreter and LLVM/native path
- [ ] CLI/user-visible behavior
- [ ] documentation and examples

Mark unaffected entries with a concrete explanation rather than deleting them.

## Proof matrix

- [ ] valid cases
- [ ] invalid case for every new diagnostic branch
- [ ] boundary cases
- [ ] adversarial cases
- [ ] generated combinations
- [ ] formatter parse/format/parse equivalence
- [ ] interpreter/native differential behavior
- [ ] Python/Rust parity where applicable
- [ ] prior-version regressions
- [ ] Windows/Linux target proof where applicable
- [ ] separate Agent B release-blocking review

## Benchmark delta

- [ ] Historical benchmark versions remain immutable.
- [ ] New tasks can falsify the capability hypothesis.
- [ ] Language-only, compiler-assisted, and full-agent results remain separate where relevant.
- [ ] Negative findings are retained.

## Exact-PR Evidence

- [ ] proof manifest
- [ ] tool versions and target triples
- [ ] test and Agent B reports
- [ ] benchmark smoke output
- [ ] generated protocol documents
- [ ] deterministic Evidence archive
- [ ] known-unproven list

## Scope protection

- [ ] Exactly one language capability is active.
- [ ] No test, critic assertion, benchmark, or security gate was weakened to obtain green status.
- [ ] No post-v1 feature was introduced implicitly.
- [ ] No custom linker, debugger, IDE, registry, or existing-tool replacement was added without a proven blocker.
