# AXIOM Automated Review Report Contract 0.1.0

Status: implemented contract and deterministic gate. This document does not claim an AI provider, PR comment publisher, cross-workflow staleness binding, branch policy, or merge authority.

## Authority boundary

The machine-readable schema at `review/contracts/0.1.0/report.schema.json` and the semantic validator in `axiom_review/contract.py` jointly define the 0.1.0 report contract. Validation is offline: external schema references, network access, model calls, and provider-specific behavior are forbidden.

A deterministic reviewer may emit blocking or advisory findings. An `advisory_ai` reviewer may emit advisory findings only. Severity describes importance but never grants authority. Model output cannot approve, reject, modify, publish, or merge code.

## Required identity and freshness fields

Every report identifies its report kind and schema version, repository, pull-request number, base SHA, exact reviewed head SHA, generation time, reviewer class, status, checks, findings, known-unreviewed sections, unavailable sections, and semantic digest.

A report with an absent or malformed exact head SHA is invalid. Later roadmap issues define live staleness checks against GitHub; this contract only preserves the identity required for those checks.

## Findings and checks

Each finding has a stable code, title, explanation, severity, authority, evidence path, optional affected file/range, and remediation. A blocking finding requires non-empty evidence. Each check records its input digest, observed conclusion, and optional evidence path.

The status enum is `passed`, `failed`, `unavailable`, or `stale`. A report marked `passed` requires at least one recorded passing check and is invalid when it contains blocking findings, any non-passing check, or unavailable sections. Rendering therefore cannot convert absent, unavailable, or failed execution into a pass.

## Canonicalization and rendering

`canonical_json` emits UTF-8 JSON with sorted keys and one final newline. `semantic_sha256` hashes compact sorted-key JSON after removing only the digest field itself. Array order remains semantically meaningful.

`validate_report` is the low-level offline validator for an explicitly supplied schema. It rejects non-local `$ref` and `$dynamicRef` targets before constructing the Draft 2020-12 validator. A local reference that cannot be resolved is converted into stable schema finding `AX-REV-CONTRACT-1002` rather than escaping as a library exception.

`render_markdown` accepts only the report. It loads the packaged schema from the immutable versioned repository path, runs the complete schema and semantic validator, and raises `InvalidReviewReport` when the schema cannot be loaded or any finding exists. A caller cannot substitute a permissive schema and render an invalid report as `PASSED`.

All report-controlled scalar text is treated as untrusted data during rendering. Newlines are flattened and Markdown control characters are escaped before insertion, so titles, explanations, remediation text, evidence paths, repository names, and identifiers cannot create forged headings, links, status lines, code spans, or review sections.

`load_and_validate_report` accepts an explicit trusted repository root so repository tools can validate a report against that repository's versioned schema. Missing, malformed, or non-object JSON is attributed to the exact failing file.

## Versioning and migration policy

Contract versions use semantic versioning.

- Patch releases may clarify prose or add validator behavior that rejects data already forbidden by the same schema and laws. They must not change valid report meaning.
- Minor releases may add optional fields or enum values. Producers must opt into the new version explicitly; consumers must reject unknown schema versions.
- Major releases may remove or rename fields, change required fields, or alter meaning.

Every version has an immutable versioned schema path. Existing schemas are not edited to simulate migration. A migration requires a pure, offline transformation with source-version validation, target-version validation, deterministic output, and tests preserving authority, reviewed-head identity, evidence references, and status meaning. No migration may convert `unavailable`, `stale`, or failed input into `passed` without new deterministic evidence.

## Deterministic review gate 0.1.0

`axiom_review/gate.py` and `tools/run_deterministic_review.py` implement the
deterministic pull-request review gate. One offline local command produces
`review-report.json` and `review-summary.md` in a caller-selected output
directory. The gate executes no model, publishes no comment, downloads no
package, and resolves no remote schema. Its only subprocesses are `git
rev-parse HEAD` and the repository's own roadmap checker.

### Gate checks

Every run records these checks with the SHA-256 of their exact input:

- `review.head-identity` — the checked-out `HEAD` equals the declared
  reviewed head SHA;
- `review.project-contract` — `check_project_contract` is recomputed at the
  reviewed head, which includes checked public claim documents;
- `review.benchmark-contract` — `check_benchmark_contract` is recomputed;
- `review.roadmap-contract` — the local v1 roadmap contract is recomputed;
- `review.proof-evidence` — a passing proof manifest exists, every
  manifest-recorded Evidence file re-hashes to its recorded digest, no
  unrecorded file exists beside them, and the recorded contract results equal
  the recomputed ones;
- `review.protected-baseline` — every file in the versioned gate policy's
  protected list still exists;
- `review.agent-b-registrations` — every policy-listed Agent B module is
  still imported and invoked by `agents/agent_b_review.py`;
- `review.workflow-security` — every workflow declares explicit permissions
  within the policy allowlist, pins every `uses:` reference to a full
  40-character commit SHA, and never declares `pull_request_target`;
- `review.report-contract` — the generated report validates against the
  packaged 0.1.0 report schema before it is written.

### Gate policy

`review/policy/0.1.0/gate-policy.json` is the versioned machine-readable
baseline validated by `review/contracts/0.1.0/gate-policy.schema.json`. It
lists protected paths, required Agent B registrations, per-workflow
permission allowlists, an unknown-workflow default allowlist of
`contents: read`, and output size limits. Removing a protected file, an Agent
B registration, or widening a permission therefore requires an explicit,
reviewable policy edit; it can never happen silently. Policy paths must be
normalized, relative, and confined to the repository root.

### Fail-closed exit codes

- `0` — every check passed and the report says `passed`;
- `1` — at least one blocking finding or non-passing check; every gate
  finding is blocking with severity `high` or `critical`;
- `2` — unusable identity input, malformed event payload, or a non-empty
  output directory, which the gate never replaces;
- `3` — internal error, report-validation failure, or exceeded output
  bounds; nothing is reported as reviewed.

### Stable gate findings

- `AX-REV-GATE-0102`: reviewed head does not match the checkout
- `AX-REV-GATE-0103`: finding overflow beyond the policy limit
- `AX-REV-GATE-0201`: project contract or checked claim documents failed
- `AX-REV-GATE-0202`: benchmark contract failed
- `AX-REV-GATE-0203`: roadmap contract failed
- `AX-REV-GATE-0301`: exact-head proof evidence is missing
- `AX-REV-GATE-0302`: proof evidence is unreadable or records a failing run
- `AX-REV-GATE-0303`: proof evidence bytes disagree with the manifest
- `AX-REV-GATE-0304`: proof evidence disagrees with recomputed head results
- `AX-REV-GATE-0401`: protected repository file was removed
- `AX-REV-GATE-0402`: Agent B registration was removed
- `AX-REV-GATE-0403`: gate policy is missing or invalid
- `AX-REV-GATE-0501`: action reference is not pinned to an immutable SHA
- `AX-REV-GATE-0502`: forbidden `pull_request_target` trigger
- `AX-REV-GATE-0503`: workflow permissions widened or undeclared
- `AX-REV-GATE-0504`: workflow could not be safely parsed

### Workflow boundary

`.github/workflows/deterministic-review.yml` runs on `pull_request` with
`contents: read` only, checks out the exact `pull_request.head.sha`, runs
`run_repo_proof.py` to produce exact-head proof evidence, runs the gate, and
uploads bounded artifacts on success and failure. It publishes no comments
and holds no write authority. The existing proof and roadmap workflows remain
separate required checks.

### Gate boundary

The gate binds proof evidence to the reviewed head by producing it in the
same checkout and by recomputed-result comparison. Cross-workflow staleness
classification, artifact-digest binding to workflow runs, and summary
publication remain governed by issues #35 and #36 and are not claimed here.

## Stable validator findings

- `AX-REV-CONTRACT-0001`: required report or schema JSON file is missing
- `AX-REV-CONTRACT-0002`: report or schema JSON is malformed
- `AX-REV-CONTRACT-0003`: report or schema JSON root is not an object
- `AX-REV-CONTRACT-1001`: external schema reference
- `AX-REV-CONTRACT-1002`: invalid Draft 2020-12 schema or unresolvable local schema reference
- `AX-REV-CONTRACT-1003`: report schema violation, including unknown fields and invalid enums
- `AX-REV-CONTRACT-2001`: AI finding attempted blocking authority
- `AX-REV-CONTRACT-2002`: non-deterministic blocking authority
- `AX-REV-CONTRACT-2003`: blocking finding lacks evidence
- `AX-REV-CONTRACT-2004`: false pass over absent checks, blockers, non-passing checks, or unavailable sections
- `AX-REV-CONTRACT-2005`: semantic digest mismatch
- `AX-REV-CONTRACT-2006`: passing report lacks exact reviewed-head identity
