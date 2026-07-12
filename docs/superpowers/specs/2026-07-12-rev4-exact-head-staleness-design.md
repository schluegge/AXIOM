# REV-4 Exact-Head Freshness Binding Design

Issue: #36  
Parent roadmap: #32  
Prerequisites: #33 and #34

## Scope

Add a deterministic freshness layer that binds every review source to one pull-request head and one workflow execution identity. It extends the existing report/gate infrastructure without publishing comments, invoking AI, changing merge policy, or modifying repository proof normalization.

## Data model

Each referenced source result records:

- stable source/check identifier;
- conclusion: `passed`, `failed`, `missing`, `pending`, `cancelled`, `skipped`, `unavailable`, or `stale`;
- reviewed head SHA;
- workflow run ID and run attempt;
- artifact name and SHA-256 digest when an artifact exists.

A freshness envelope records the repository, pull-request number, base SHA, current reviewed head SHA, publisher run ID/attempt, and all source results. The envelope is deterministic JSON input to report generation. Manually pasted PR-body hashes are never accepted as source authority.

## Deterministic rules

1. Every passing source must identify the current 40-character reviewed head SHA.
2. A source bound to any other head is classified `stale`; mixed source SHAs are blocking.
3. `cancelled`, `skipped`, `missing`, `pending`, `unavailable`, or `stale` can never contribute to a passing deterministic review.
4. A source claiming an artifact must include a valid `sha256:<64 lowercase hex>` digest.
5. Reruns retain the same reviewed commit and are distinguished by `(run_id, run_attempt)`.
6. A publisher candidate may replace an existing summary only when it targets the same current head and its execution tuple is newer. An older delayed run is rejected deterministically.
7. Force-updated branches immediately stale every source and publication bound to the previous head.

## Components

- `axiom_review/freshness.py`: pure validation and publication-order functions with no network, subprocess, filesystem, or model access.
- `tests/test_review_freshness.py`: current-head, previous-head, mixed-SHA, cancelled/skipped, rerun, delayed publisher, rapid-push, and missing-artifact regressions.
- Later implementation commits will integrate the validated envelope into the versioned report schema, deterministic Markdown, gate evidence, workflow metadata, and Agent B attacks.

## Stable diagnostics

- `AX-REV-FRESH-0101`: source result lacks valid execution identity.
- `AX-REV-FRESH-0102`: source result targets a previous or different head.
- `AX-REV-FRESH-0103`: source results contain mixed reviewed-head SHAs.
- `AX-REV-FRESH-0104`: non-passing source was represented as current passing evidence.
- `AX-REV-FRESH-0105`: required artifact digest is missing or malformed.
- `AX-REV-FRESH-0201`: delayed or older publisher attempted to replace newer state.
- `AX-REV-FRESH-0202`: publisher target is not the current pull-request head.

## Failure behavior

Validation is fail-closed and returns stable deterministic findings. It never upgrades a non-passing state. Publication ordering returns a rejection finding rather than mutating remote state. Internal malformed values are treated as invalid evidence, not exceptions that can be rendered as passed.

## Acceptance mapping

- Current head: a complete same-head envelope passes.
- Previous head and mixed SHAs: stable stale/mixed findings.
- Delayed publisher and rapid pushes: deterministic replacement rejection.
- Reruns: attempt identity is preserved without changing reviewed head.
- Cancelled/skipped/missing artifacts: cannot pass.
- JSON/Markdown/PR-summary visibility: implemented by schema/render/gate integration after the pure RED contract is fixed.

## Non-goals

No PR comment publication, AI provider, auto-merge, branch-protection change, M2 work, or modification of `run_repo_proof.py` Evidence normalization.