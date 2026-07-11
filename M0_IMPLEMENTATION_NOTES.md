# M0 Implementation Notes

Tracking issue: #11  
Parent program: #9  
Target release: AXIOM v1.0

## Delivered capability

M0 adds one read-only project-state contract and consistency gate for the
existing AXIOM v0.7 semantic oracle. It does not add source syntax, runtime
behavior, a benchmark runner, package resolution, editor tooling, or a new
compiler stage.

## Contract boundary

`contracts/project.json` indexes:

- current language version and semantic authority;
- document authority order;
- proven target scope;
- six current proven feature groups;
- normative specification, implementation, tests, proof IDs, diagnostic
  ownership, and targets for each feature;
- explicitly deferred v1 and post-v1 work;
- the checked public claim blocks in README and `PROOF_STATUS.md`.

The contract is an index into authority. It does not replace the normative
semantic documents.

## Checker boundary

`tools/check_project_contract.py`:

- validates with `jsonschema.Draft202012Validator`;
- rejects external `$ref` values before validator construction;
- performs no network access;
- writes no repository source;
- emits deterministic text or JSON;
- uses stable exit codes: 0 pass, 2 input/dependency, 3 schema, 4 consistency;
- checks repository paths, version agreement, target evidence, claim blocks,
  diagnostic ownership, feature/deferred separation, and roadmap alignment.

## Evidence boundary

The canonical `run_repo_proof.py` executes the contract gate before unit tests
and Agent B. Its JSON/text report and loaded dependency versions are included in
the same deterministic Evidence archive and manifest as the existing compiler
proof.

## Explicit non-goals

- no AXIOM syntax or semantic expansion;
- no Rust bootstrap implementation;
- no AXIOM-Bench tasks;
- no mdBook, LSP, Tree-sitter, dashboard, or project-management service;
- no package manager or registry;
- no generalized policy language;
- no user-visible raw pointers or `unsafe`.
