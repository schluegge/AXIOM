# AXIOM Automated Review Report Contract 0.1.0

Status: implemented contract only. This document does not claim an operational workflow, AI provider, PR publisher, branch policy, or merge authority.

## Authority boundary

The machine-readable schema at `review/contracts/0.1.0/report.schema.json` and the semantic validator in `axiom_review/contract.py` jointly define the 0.1.0 report contract. Validation is offline: external schema references, network access, model calls, and provider-specific behavior are forbidden.

A deterministic reviewer may emit blocking or advisory findings. An `advisory_ai` reviewer may emit advisory findings only. Severity describes importance but never grants authority. Model output cannot approve, reject, modify, publish, or merge code.

## Required identity and freshness fields

Every report identifies its report kind and schema version, repository, pull-request number, base SHA, exact reviewed head SHA, generation time, reviewer class, status, checks, findings, known-unreviewed sections, unavailable sections, and semantic digest.

A report with an absent or malformed exact head SHA is invalid. Later roadmap issues define live staleness checks against GitHub; this contract only preserves the identity required for those checks.

## Findings and checks

Each finding has a stable code, title, explanation, severity, authority, evidence path, optional affected file/range, and remediation. A blocking finding requires non-empty evidence. Each check records its input digest, observed conclusion, and optional evidence path.

The status enum is `passed`, `failed`, `unavailable`, or `stale`. A report marked `passed` is invalid when it contains blocking findings or unavailable sections. Rendering therefore cannot convert unavailable execution into a pass.

## Canonicalization and rendering

`canonical_json` emits UTF-8 JSON with sorted keys and one final newline. `semantic_sha256` hashes compact sorted-key JSON after removing only the digest field itself. Array order remains semantically meaningful.

`render_markdown` produces a deterministic summary. It does not infer missing success and does not combine deterministic authority with advisory AI wording.

## Versioning and migration policy

Contract versions use semantic versioning.

- Patch releases may clarify prose or add validator behavior that rejects data already forbidden by the same schema and laws. They must not change valid report meaning.
- Minor releases may add optional fields or enum values. Producers must opt into the new version explicitly; consumers must reject unknown schema versions.
- Major releases may remove or rename fields, change required fields, or alter meaning.

Every version has an immutable versioned schema path. Existing schemas are not edited to simulate migration. A migration requires a pure, offline transformation with source-version validation, target-version validation, deterministic output, and tests preserving authority, reviewed-head identity, evidence references, and status meaning. No migration may convert `unavailable`, `stale`, or failed input into `passed` without new deterministic evidence.

## Stable validator findings

- `AX-REV-CONTRACT-1001`: external schema reference
- `AX-REV-CONTRACT-1002`: invalid Draft 2020-12 schema
- `AX-REV-CONTRACT-1003`: report schema violation, including unknown fields and invalid enums
- `AX-REV-CONTRACT-2001`: AI finding attempted blocking authority
- `AX-REV-CONTRACT-2002`: non-deterministic blocking authority
- `AX-REV-CONTRACT-2003`: blocking finding lacks evidence
- `AX-REV-CONTRACT-2004`: false pass over blockers or unavailable sections
- `AX-REV-CONTRACT-2005`: semantic digest mismatch
- `AX-REV-CONTRACT-2006`: passing report lacks exact reviewed-head identity
