from pathlib import Path
from typing import Any

from .contract import (
    SCHEMA_VERSION,
    Finding,
    InvalidReviewReport,
    canonical_json,
    load_and_validate_report,
    render_markdown,
    semantic_sha256,
    validate_report,
)
from . import gate as _gate
from .gate import (
    EXIT_BLOCKED,
    EXIT_INTERNAL,
    EXIT_PASSED,
    EXIT_USAGE,
    GateInputError,
    GateInternalError,
    GateResult,
    load_event,
    load_gate_policy,
    run_deterministic_review,
)


def _check_protected_baseline(
    root: Path,
    policy: dict[str, Any] | None,
    policy_findings: list[dict[str, Any]],
) -> _gate.CheckOutcome:
    """Require protected exact files and directory-prefix roots to exist."""

    findings = list(policy_findings)
    missing: list[str] = []
    if policy is not None:
        for relative in policy["protected_paths"]:
            candidate = _gate._safe_relative_path(root, relative)
            exists_with_expected_type = (
                candidate is not None
                and (candidate.is_dir() if relative.endswith("/") else candidate.is_file())
            )
            if not exists_with_expected_type:
                missing.append(relative)
        for relative in missing[: _gate._MAX_FINDINGS_PER_CHECK]:
            findings.append(
                _gate._finding(
                    "AX-REV-GATE-0401",
                    "Protected repository path was removed",
                    f"protected path is missing from the reviewed tree: {relative}",
                    "checks/protected-baseline.json",
                    "Restore the path or change the gate policy in an explicit reviewed edit.",
                )
            )
    return _gate.CheckOutcome(
        check_id="review.protected-baseline",
        title="Protected tests, proof stages, schemas, and workflows",
        input_sha256=_gate._digest_file(root / _gate.POLICY_PATH),
        conclusion="passed" if not findings else "failed",
        evidence_name="protected-baseline.json",
        evidence={"missing": missing, "policy_valid": policy is not None},
        findings=findings,
    )


# Package initialization runs before direct ``axiom_review.gate`` imports. Patch the
# module global used by ``run_deterministic_review`` so exact-file and directory-prefix
# baseline semantics are identical for both public import paths.
_gate.check_protected_baseline = _check_protected_baseline

__all__ = [
    "SCHEMA_VERSION",
    "Finding",
    "InvalidReviewReport",
    "canonical_json",
    "load_and_validate_report",
    "render_markdown",
    "semantic_sha256",
    "validate_report",
    "EXIT_BLOCKED",
    "EXIT_INTERNAL",
    "EXIT_PASSED",
    "EXIT_USAGE",
    "GateInputError",
    "GateInternalError",
    "GateResult",
    "load_event",
    "load_gate_policy",
    "run_deterministic_review",
]
