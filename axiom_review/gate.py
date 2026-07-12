from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from axiom_bench import check_benchmark_contract
from axiom_contract import check_project_contract

from .contract import (
    SCHEMA_PATH,
    canonical_json,
    render_markdown,
    semantic_sha256,
    validate_report,
)

GATE_SCHEMA_VERSION = "0.1.0"
POLICY_PATH = Path("review/policy/0.1.0/gate-policy.json")
POLICY_SCHEMA_PATH = Path("review/contracts/0.1.0/gate-policy.schema.json")

EXIT_PASSED = 0
EXIT_BLOCKED = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")
_PINNED_USES = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_PERMISSION_RANK = {"none": 0, "read": 1, "write": 2}
_SUBPROCESS_TIMEOUT_SECONDS = 300
_MAX_TEXT_EVIDENCE_CHARS = 20_000
_MAX_FINDINGS_PER_CHECK = 50


class GateInputError(ValueError):
    """Raised when caller-supplied identity or option input is unusable."""


class GateInternalError(RuntimeError):
    """Raised when the gate cannot produce a contract-valid bounded report."""


@dataclass
class CheckOutcome:
    """One executed deterministic check plus its findings and raw evidence."""

    check_id: str
    title: str
    input_sha256: str
    conclusion: str
    evidence_name: str
    evidence: dict[str, Any]
    findings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GateResult:
    """The complete outcome of one deterministic review execution."""

    report: dict[str, Any]
    summary: str
    exit_code: int
    report_path: Path | None
    summary_path: Path | None
    errors: list[str] = field(default_factory=list)


def _digest_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _digest_file(path: Path) -> str:
    try:
        return _digest_bytes(path.read_bytes())
    except OSError:
        return _digest_bytes(b"absent")


def _bounded_text(text: str) -> str:
    if len(text) <= _MAX_TEXT_EVIDENCE_CHARS:
        return text
    return text[:_MAX_TEXT_EVIDENCE_CHARS] + "…[truncated]"


def _finding(
    code: str,
    title: str,
    explanation: str,
    evidence_path: str,
    remediation: str,
    severity: str = "high",
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "explanation": explanation,
        "severity": severity,
        "authority": "blocking",
        "evidence_path": evidence_path,
        "affected_location": None,
        "remediation": remediation,
    }


def _safe_relative_path(root: Path, relative: str) -> Path | None:
    if "\\" in relative:
        return None
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or "." in pure.parts or ".." in pure.parts:
        return None
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def load_event(path: Path) -> dict[str, Any]:
    """Parse a GitHub pull_request event payload into a review identity."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GateInputError(f"event file is missing: {path}") from error
    except OSError as error:
        raise GateInputError(f"event file could not be read: {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise GateInputError(f"event file is not valid JSON: {path}: {error.msg}") from error
    if not isinstance(value, dict):
        raise GateInputError("event payload root must be an object")
    pull_request = value.get("pull_request")
    repository = value.get("repository")
    if not isinstance(pull_request, dict) or not isinstance(repository, dict):
        raise GateInputError("event payload must contain pull_request and repository objects")
    number = pull_request.get("number")
    head = pull_request.get("head")
    base = pull_request.get("base")
    full_name = repository.get("full_name")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise GateInputError("event pull_request.number must be a positive integer")
    if not isinstance(head, dict) or not isinstance(base, dict):
        raise GateInputError("event pull_request.head and pull_request.base must be objects")
    head_sha = head.get("sha")
    base_sha = base.get("sha")
    if not isinstance(head_sha, str) or _SHA40.fullmatch(head_sha) is None:
        raise GateInputError("event pull_request.head.sha must be a 40-character SHA")
    if not isinstance(base_sha, str) or _SHA40.fullmatch(base_sha) is None:
        raise GateInputError("event pull_request.base.sha must be a 40-character SHA")
    if not isinstance(full_name, str) or _REPOSITORY.fullmatch(full_name) is None:
        raise GateInputError("event repository.full_name must be owner/name")
    return {
        "repository": full_name,
        "pull_request_number": number,
        "base_sha": base_sha,
        "head_sha": head_sha,
    }


def check_head_identity(root: Path, head_sha: str) -> CheckOutcome:
    """Verify that the checked-out repository HEAD equals the declared head."""

    resolved: str | None = None
    error: str | None = None
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as failure:
        error = f"git rev-parse could not run: {failure}"
    else:
        if completed.returncode == 0:
            candidate = completed.stdout.strip()
            if _SHA40.fullmatch(candidate) is not None:
                resolved = candidate
            else:
                error = f"git rev-parse produced no usable SHA: {candidate!r}"
        else:
            error = _bounded_text(completed.stderr.strip() or "git rev-parse failed")
    evidence = {
        "expected_head_sha": head_sha,
        "resolved_head_sha": resolved,
        "error": error,
    }
    findings: list[dict[str, Any]] = []
    if resolved != head_sha:
        findings.append(
            _finding(
                "AX-REV-GATE-0102",
                "Reviewed head does not match the checkout",
                f"declared head {head_sha} but the working tree resolves to {resolved!r}"
                + (f" ({error})" if error else ""),
                "checks/head-identity.json",
                "Run the review against the exact declared pull-request head commit.",
            )
        )
    return CheckOutcome(
        check_id="review.head-identity",
        title="Exact reviewed-head identity",
        input_sha256=_digest_bytes(head_sha.encode("utf-8")),
        conclusion="passed" if not findings else "failed",
        evidence_name="head-identity.json",
        evidence=evidence,
        findings=findings,
    )


def _contract_outcome(
    check_id: str,
    title: str,
    code: str,
    input_path: Path,
    result: dict[str, Any],
    evidence_name: str,
    remediation: str,
) -> CheckOutcome:
    findings: list[dict[str, Any]] = []
    if result.get("status") != "passed":
        codes = sorted({item.get("code", "?") for item in result.get("findings", [])})[:10]
        findings.append(
            _finding(
                code,
                f"{title} failed",
                f"validation reported status {result.get('status')!r} with findings {codes}",
                f"checks/{evidence_name}",
                "Fix the reported contract findings; do not weaken the checker.",
            )
        )
    return CheckOutcome(
        check_id=check_id,
        title=title,
        input_sha256=_digest_file(input_path),
        conclusion="passed" if not findings else "failed",
        evidence_name=evidence_name,
        evidence=result,
        findings=findings,
    )


def check_project_contract_gate(root: Path) -> tuple[CheckOutcome, dict[str, Any]]:
    """Recompute the machine-readable project contract at the reviewed head."""

    result = check_project_contract(root)
    outcome = _contract_outcome(
        "review.project-contract",
        "Project contract and checked public claims",
        "AX-REV-GATE-0201",
        root / "contracts" / "project.json",
        result,
        "project-contract.json",
        "Align contracts/project.json and checked claim documents.",
    )
    return outcome, result


def check_benchmark_contract_gate(root: Path) -> tuple[CheckOutcome, dict[str, Any]]:
    """Recompute the benchmark contract and schema index at the reviewed head."""

    result = check_benchmark_contract(root)
    outcome = _contract_outcome(
        "review.benchmark-contract",
        "Benchmark contract and schema index",
        "AX-REV-GATE-0202",
        root / "benchmarks" / "contracts" / "0.1.0" / "contract.json",
        result,
        "benchmark-contract.json",
        "Align the benchmark contract, schemas, and preregistration.",
    )
    return outcome, result


def check_roadmap_contract_gate(root: Path) -> CheckOutcome:
    """Run the local v1 roadmap contract checker at the reviewed head."""

    command = [
        sys.executable,
        str(root / "tools" / "check_v1_roadmap.py"),
        "--contract",
        str(root / "roadmap" / "v1.json"),
    ]
    report: dict[str, Any] | None = None
    error: str | None = None
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as failure:
        error = f"roadmap checker could not run: {failure}"
    else:
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        try:
            parsed = json.loads(completed.stdout)
            if isinstance(parsed, dict):
                report = parsed
            else:
                error = "roadmap checker output is not an object"
        except json.JSONDecodeError as failure:
            error = f"roadmap checker output is not JSON: {failure.msg}"
    passed = (
        error is None
        and exit_code == 0
        and report is not None
        and report.get("status") == "passed"
    )
    findings: list[dict[str, Any]] = []
    if not passed:
        codes = (
            sorted({item.get("code", "?") for item in report.get("findings", [])})[:10]
            if report is not None
            else []
        )
        findings.append(
            _finding(
                "AX-REV-GATE-0203",
                "Roadmap contract failed",
                f"exit code {exit_code!r}, findings {codes}"
                + (f", error: {error}" if error else ""),
                "checks/roadmap-contract.json",
                "Fix roadmap/v1.json and tracked documents; keep one active milestone.",
            )
        )
    return CheckOutcome(
        check_id="review.roadmap-contract",
        title="v1 roadmap contract (local)",
        input_sha256=_digest_file(root / "roadmap" / "v1.json"),
        conclusion="passed" if passed else "failed",
        evidence_name="roadmap-contract.json",
        evidence={
            "exit_code": exit_code,
            "report": report,
            "stdout_tail": _bounded_text(stdout),
            "stderr_tail": _bounded_text(stderr),
            "error": error,
        },
        findings=findings,
    )


def check_proof_evidence(
    evidence_dir: Path,
    project_result: dict[str, Any],
    benchmark_result: dict[str, Any],
) -> CheckOutcome:
    """Verify passing, internally consistent exact-head proof evidence."""

    manifest_path = evidence_dir / "manifest.json"
    findings: list[dict[str, Any]] = []
    conclusion = "passed"
    evidence: dict[str, Any] = {
        "manifest": "manifest.json",
        "verified_files": 0,
        "mismatched_files": [],
        "unexpected_files": [],
    }

    def blocked(code: str, title: str, explanation: str, remediation: str) -> None:
        findings.append(
            _finding(code, title, explanation, "checks/proof-evidence.json", remediation)
        )

    manifest: dict[str, Any] | None = None
    if not manifest_path.is_file():
        conclusion = "missing"
        blocked(
            "AX-REV-GATE-0301",
            "Exact-head proof evidence is missing",
            f"no proof manifest exists at {manifest_path.name}; run_repo_proof.py "
            "must run at the reviewed head before the deterministic review",
            "Run python3 run_repo_proof.py at the reviewed head, then rerun the review.",
        )
    else:
        try:
            parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = parsed if isinstance(parsed, dict) else None
        except (OSError, json.JSONDecodeError):
            manifest = None
        if manifest is None:
            conclusion = "failed"
            blocked(
                "AX-REV-GATE-0302",
                "Proof manifest is unreadable",
                "the proof manifest is not a JSON object",
                "Regenerate proof evidence with run_repo_proof.py.",
            )

    if manifest is not None:
        recorded_project = manifest.get("project_contract")
        recorded_benchmark = manifest.get("benchmark_contract")
        agent_b = manifest.get("agent_b")
        files = manifest.get("files")
        if (
            not isinstance(recorded_project, dict)
            or not isinstance(recorded_benchmark, dict)
            or not isinstance(agent_b, dict)
            or not isinstance(files, dict)
        ):
            conclusion = "failed"
            blocked(
                "AX-REV-GATE-0302",
                "Proof manifest is structurally incomplete",
                "project_contract, benchmark_contract, agent_b, or files is absent",
                "Regenerate proof evidence with run_repo_proof.py.",
            )
        else:
            if (
                manifest.get("status") != "passed"
                or manifest.get("unit_test_exit_code") != 0
                or agent_b.get("exit_code") != 0
            ):
                conclusion = "failed"
                blocked(
                    "AX-REV-GATE-0302",
                    "Proof evidence does not record a passing run",
                    f"status={manifest.get('status')!r}, "
                    f"unit_test_exit_code={manifest.get('unit_test_exit_code')!r}, "
                    f"agent_b.exit_code={agent_b.get('exit_code')!r}",
                    "Make the complete repository proof pass at the reviewed head.",
                )

            mismatched: list[str] = []
            verified = 0
            for relative, expected in sorted(files.items()):
                if not isinstance(relative, str) or not isinstance(expected, str):
                    mismatched.append(str(relative))
                    continue
                candidate = _safe_relative_path(evidence_dir, relative)
                if candidate is None or not candidate.is_file():
                    mismatched.append(relative)
                elif _digest_file(candidate) != expected:
                    mismatched.append(relative)
                else:
                    verified += 1
            unexpected = sorted(
                path.relative_to(evidence_dir).as_posix()
                for path in evidence_dir.rglob("*")
                if path.is_file()
                and path != manifest_path
                and path.relative_to(evidence_dir).as_posix() not in files
            )
            evidence["verified_files"] = verified
            evidence["mismatched_files"] = mismatched[:_MAX_FINDINGS_PER_CHECK]
            evidence["unexpected_files"] = unexpected[:_MAX_FINDINGS_PER_CHECK]
            if mismatched or unexpected:
                conclusion = "failed"
                blocked(
                    "AX-REV-GATE-0303",
                    "Proof evidence bytes disagree with the manifest",
                    f"mismatched={mismatched[:5]}, unexpected={unexpected[:5]}",
                    "Regenerate proof evidence; never edit Evidence files in place.",
                )

            drift: list[str] = []
            if recorded_project.get("status") != project_result.get("status"):
                drift.append("project_contract.status")
            if recorded_project.get("current_features") != project_result.get(
                "counts", {}
            ).get("current_features"):
                drift.append("project_contract.current_features")
            if recorded_benchmark.get("status") != benchmark_result.get("status"):
                drift.append("benchmark_contract.status")
            if recorded_benchmark.get("schemas_checked") != benchmark_result.get(
                "schemas_checked"
            ):
                drift.append("benchmark_contract.schemas_checked")
            evidence["drift"] = drift
            if drift:
                conclusion = "failed"
                blocked(
                    "AX-REV-GATE-0304",
                    "Proof evidence disagrees with the reviewed head",
                    f"recorded proof results drifted from recomputed results: {drift}",
                    "Regenerate proof evidence at the exact reviewed head.",
                )

    return CheckOutcome(
        check_id="review.proof-evidence",
        title="Exact-head repository proof evidence",
        input_sha256=_digest_file(manifest_path),
        conclusion=conclusion,
        evidence_name="proof-evidence.json",
        evidence=evidence,
        findings=findings,
    )


def load_gate_policy(root: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Load and validate the versioned machine-readable gate policy."""

    findings: list[dict[str, Any]] = []

    def invalid(explanation: str) -> tuple[None, list[dict[str, Any]]]:
        findings.append(
            _finding(
                "AX-REV-GATE-0403",
                "Gate policy is missing or invalid",
                explanation,
                "checks/protected-baseline.json",
                "Restore a schema-valid review/policy/0.1.0/gate-policy.json.",
                severity="critical",
            )
        )
        return None, findings

    try:
        policy = json.loads((root / POLICY_PATH).read_text(encoding="utf-8"))
        schema = json.loads((root / POLICY_SCHEMA_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return invalid(f"policy or policy schema is unreadable: {error}")
    if not isinstance(policy, dict) or not isinstance(schema, dict):
        return invalid("policy and policy schema roots must be objects")
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(policy),
            key=lambda item: (item.json_path, item.message),
        )
    except SchemaError as error:
        return invalid(f"policy schema is invalid: {error.message}")
    if errors:
        return invalid(
            f"policy violates its schema: {errors[0].json_path}: {errors[0].message}"
        )
    for relative in [
        *policy["protected_paths"],
        *policy["workflow_rules"]["workflows"],
    ]:
        if _safe_relative_path(root, relative) is None:
            return invalid(f"policy path escapes the repository root: {relative}")
    return policy, findings


def check_protected_baseline(
    root: Path, policy: dict[str, Any] | None, policy_findings: list[dict[str, Any]]
) -> CheckOutcome:
    """Require every protected proof, test, schema, and workflow file to exist."""

    findings = list(policy_findings)
    missing: list[str] = []
    if policy is not None:
        for relative in policy["protected_paths"]:
            candidate = _safe_relative_path(root, relative)
            if candidate is None or not candidate.is_file():
                missing.append(relative)
        for relative in missing[:_MAX_FINDINGS_PER_CHECK]:
            findings.append(
                _finding(
                    "AX-REV-GATE-0401",
                    "Protected repository file was removed",
                    f"protected path is missing from the reviewed tree: {relative}",
                    "checks/protected-baseline.json",
                    "Restore the file or change the gate policy in an explicit reviewed edit.",
                )
            )
    return CheckOutcome(
        check_id="review.protected-baseline",
        title="Protected tests, proof stages, schemas, and workflows",
        input_sha256=_digest_file(root / POLICY_PATH),
        conclusion="passed" if not findings else "failed",
        evidence_name="protected-baseline.json",
        evidence={"missing": missing, "policy_valid": policy is not None},
        findings=findings,
    )


def check_agent_b_registrations(root: Path, policy: dict[str, Any] | None) -> CheckOutcome:
    """Require every policy-listed Agent B module to stay imported and invoked."""

    source_path = root / "agents" / "agent_b_review.py"
    registered: dict[str, str] = {}
    called: set[str] = set()
    error: str | None = None
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as failure:
        error = f"agents/agent_b_review.py could not be parsed: {failure}"
    else:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    if alias.name == "register":
                        registered[node.module] = alias.asname or alias.name
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(node.func.id)
    findings: list[dict[str, Any]] = []
    missing: list[str] = []
    if policy is not None:
        if error is not None:
            missing = list(policy["agent_b_registration_modules"])
        else:
            for module in policy["agent_b_registration_modules"]:
                alias = registered.get(module)
                if alias is None or alias not in called:
                    missing.append(module)
        for module in missing[:_MAX_FINDINGS_PER_CHECK]:
            findings.append(
                _finding(
                    "AX-REV-GATE-0402",
                    "Agent B registration was removed",
                    f"module is no longer imported and invoked by agent_b_review.py: {module}"
                    + (f" ({error})" if error else ""),
                    "checks/agent-b-registrations.json",
                    "Restore the Agent B registration; Agent B checks are release blocking.",
                )
            )
        conclusion = "passed" if not findings else "failed"
    else:
        conclusion = "skipped"
    return CheckOutcome(
        check_id="review.agent-b-registrations",
        title="Agent B adversarial check registrations",
        input_sha256=_digest_file(source_path),
        conclusion=conclusion,
        evidence_name="agent-b-registrations.json",
        evidence={
            "registered": dict(sorted(registered.items())),
            "missing": missing,
            "error": error,
        },
        findings=findings,
    )


def _permission_findings(
    declared: Any, allowlist: dict[str, str], location: str
) -> list[str]:
    problems: list[str] = []
    if not isinstance(declared, dict):
        problems.append(
            f"{location}: permissions must be an explicit least-privilege mapping"
        )
        return problems
    for scope, value in declared.items():
        if not isinstance(scope, str) or value not in _PERMISSION_RANK:
            problems.append(f"{location}: unsupported permission entry {scope!r}: {value!r}")
            continue
        allowed = allowlist.get(scope, "none")
        if _PERMISSION_RANK[value] > _PERMISSION_RANK[allowed]:
            problems.append(
                f"{location}: {scope}: {value} exceeds the allowlisted maximum {allowed!r}"
            )
    return problems


def _workflow_trigger_names(parsed: dict[str, Any]) -> tuple[list[str], str | None]:
    triggers = parsed.get(True, parsed.get("on"))
    if isinstance(triggers, str):
        return [triggers], None
    if isinstance(triggers, list):
        if all(isinstance(item, str) for item in triggers):
            return list(triggers), None
        return [], "trigger list contains a non-string entry"
    if isinstance(triggers, dict):
        names = [key if isinstance(key, str) else repr(key) for key in triggers]
        return names, None
    return [], "workflow does not declare a recognizable trigger mapping"


def check_workflow_security(root: Path, policy: dict[str, Any] | None) -> CheckOutcome:
    """Enforce pinned actions, explicit least permissions, and trigger safety."""

    findings: list[dict[str, Any]] = []
    scans: list[dict[str, Any]] = []
    directory = root / ".github" / "workflows"
    workflow_paths = (
        sorted(
            path
            for pattern in ("*.yml", "*.yaml")
            for path in directory.glob(pattern)
            if path.is_file()
        )
        if directory.is_dir()
        else []
    )

    def blocked(code: str, title: str, explanation: str, remediation: str) -> None:
        findings.append(
            _finding(
                code,
                title,
                explanation,
                "checks/workflow-security.json",
                remediation,
                severity="critical",
            )
        )

    if policy is not None:
        rules = policy["workflow_rules"]
        for path in workflow_paths:
            relative = path.relative_to(root).as_posix()
            scan: dict[str, Any] = {"workflow": relative}
            scans.append(scan)
            try:
                parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as error:
                parsed = None
                scan["error"] = _bounded_text(str(error))
            if not isinstance(parsed, dict):
                blocked(
                    "AX-REV-GATE-0504",
                    "Workflow could not be safely parsed",
                    f"{relative} is not a parseable workflow mapping; the gate fails closed",
                    "Restore a well-formed workflow file.",
                )
                continue

            trigger_names, trigger_error = _workflow_trigger_names(parsed)
            scan["triggers"] = trigger_names
            if trigger_error is not None:
                blocked(
                    "AX-REV-GATE-0504",
                    "Workflow trigger declaration is not recognizable",
                    f"{relative}: {trigger_error}",
                    "Declare workflow triggers with plain string names.",
                )
            if "pull_request_target" in trigger_names:
                blocked(
                    "AX-REV-GATE-0502",
                    "Forbidden pull_request_target trigger",
                    f"{relative} declares pull_request_target, which runs privileged "
                    "automation against attacker-controlled pull-request content",
                    "Use the plain pull_request trigger with read-only permissions.",
                )

            allowlist = rules["workflows"].get(
                relative, {"permissions": rules["default_permission_allowlist"]}
            )["permissions"]
            problems = _permission_findings(
                parsed.get("permissions"), allowlist, f"{relative} (workflow)"
            )
            jobs = parsed.get("jobs")
            if not isinstance(jobs, dict):
                blocked(
                    "AX-REV-GATE-0504",
                    "Workflow jobs are not a mapping",
                    f"{relative} has no parseable jobs mapping; the gate fails closed",
                    "Restore a well-formed jobs section.",
                )
                continue
            unpinned: list[str] = []
            for job_name, job in jobs.items():
                if not isinstance(job, dict):
                    blocked(
                        "AX-REV-GATE-0504",
                        "Workflow job is not a mapping",
                        f"{relative}: job {job_name!r} is not parseable; the gate fails closed",
                        "Restore a well-formed job definition.",
                    )
                    continue
                if "permissions" in job:
                    problems.extend(
                        _permission_findings(
                            job["permissions"], allowlist, f"{relative} (job {job_name})"
                        )
                    )
                references = [job.get("uses")] + [
                    step.get("uses")
                    for step in (job.get("steps") or [])
                    if isinstance(step, dict)
                ]
                for reference in references:
                    if reference is None:
                        continue
                    if not isinstance(reference, str) or _PINNED_USES.fullmatch(
                        reference
                    ) is None:
                        unpinned.append(f"{job_name}: {reference!r}")
            scan["permission_problems"] = problems
            scan["unpinned_references"] = unpinned
            for problem in problems[:_MAX_FINDINGS_PER_CHECK]:
                blocked(
                    "AX-REV-GATE-0503",
                    "Workflow permissions widened or undeclared",
                    problem,
                    "Declare explicit read-only permissions within the policy allowlist.",
                )
            for reference in unpinned[:_MAX_FINDINGS_PER_CHECK]:
                blocked(
                    "AX-REV-GATE-0501",
                    "Action reference is not pinned to an immutable SHA",
                    f"{relative}: {reference} does not end in a full 40-character commit SHA",
                    "Pin every uses: reference to a full-length commit SHA.",
                )
        conclusion = "passed" if not findings else "failed"
    else:
        conclusion = "skipped"
    return CheckOutcome(
        check_id="review.workflow-security",
        title="Workflow permissions, triggers, and action pinning",
        input_sha256=_digest_file(root / POLICY_PATH),
        conclusion=conclusion,
        evidence_name="workflow-security.json",
        evidence={"workflows": scans},
        findings=findings,
    )


def _validate_identity(
    repository: str, pull_request_number: int, base_sha: str, head_sha: str
) -> list[str]:
    problems: list[str] = []
    if not isinstance(repository, str) or _REPOSITORY.fullmatch(repository) is None:
        problems.append(f"repository must be owner/name: {repository!r}")
    if (
        not isinstance(pull_request_number, int)
        or isinstance(pull_request_number, bool)
        or pull_request_number < 1
    ):
        problems.append(f"pull request number must be a positive integer: {pull_request_number!r}")
    for label, value in (("base", base_sha), ("head", head_sha)):
        if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
            problems.append(f"{label} SHA must be 40 lowercase hex characters: {value!r}")
    return problems


def _prepare_output_directory(output_dir: Path, evidence_dir: Path) -> list[str]:
    problems: list[str] = []
    resolved_output = output_dir.resolve()
    resolved_evidence = evidence_dir.resolve()
    for inner, outer in (
        (resolved_output, resolved_evidence),
        (resolved_evidence, resolved_output),
    ):
        if inner == outer or outer in inner.parents:
            problems.append(
                f"output directory and proof evidence directory may not nest: "
                f"{resolved_output} / {resolved_evidence}"
            )
            return problems
    if output_dir.exists():
        if not output_dir.is_dir():
            problems.append(f"output path exists and is not a directory: {output_dir}")
        elif any(output_dir.iterdir()):
            problems.append(
                f"output directory already contains files and is never replaced: {output_dir}"
            )
    return problems


def _write_bounded_evidence(path: Path, payload: dict[str, Any], limit: int) -> None:
    text = canonical_json(payload)
    if len(text.encode("utf-8")) > limit:
        text = canonical_json(
            {
                "truncated": True,
                "reason": "evidence payload exceeded the policy size limit",
                "payload_sha256": _digest_bytes(text.encode("utf-8")),
            }
        )
    path.write_text(text, encoding="utf-8")


def run_deterministic_review(
    root: Path,
    *,
    repository: str,
    pull_request_number: int,
    base_sha: str,
    head_sha: str,
    evidence_dir: Path | None = None,
    output_dir: Path | None = None,
    generated_at: str | None = None,
) -> GateResult:
    """Execute every deterministic check and emit a validated bounded report."""

    root = root.resolve()
    evidence_dir = (evidence_dir or root / "evidence" / "repo-proof").resolve()
    output_dir = output_dir if output_dir is not None else root / "evidence" / "deterministic-review"

    problems = _validate_identity(repository, pull_request_number, base_sha, head_sha)
    problems.extend(_prepare_output_directory(output_dir, evidence_dir))
    if problems:
        return GateResult({}, "", EXIT_USAGE, None, None, errors=problems)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "checks").mkdir()

    project_outcome, project_result = check_project_contract_gate(root)
    benchmark_outcome, benchmark_result = check_benchmark_contract_gate(root)
    policy, policy_findings = load_gate_policy(root)
    outcomes = [
        check_head_identity(root, head_sha),
        project_outcome,
        benchmark_outcome,
        check_roadmap_contract_gate(root),
        check_proof_evidence(evidence_dir, project_result, benchmark_result),
        check_protected_baseline(root, policy, policy_findings),
        check_agent_b_registrations(root, policy),
        check_workflow_security(root, policy),
    ]

    limits = (
        policy["limits"]
        if policy is not None
        else {
            "max_report_bytes": 1_048_576,
            "max_summary_bytes": 262_144,
            "max_findings": 200,
            "max_evidence_file_bytes": 1_048_576,
        }
    )

    findings: list[dict[str, Any]] = []
    for outcome in outcomes:
        findings.extend(outcome.findings)
    if len(findings) > limits["max_findings"]:
        kept = findings[: limits["max_findings"] - 1]
        kept.append(
            _finding(
                "AX-REV-GATE-0103",
                "Finding overflow",
                f"{len(findings)} findings exceeded the report limit "
                f"{limits['max_findings']}; the remainder is in check evidence",
                "checks",
                "Fix the reported findings and rerun the review.",
            )
        )
        findings = kept

    for outcome in outcomes:
        _write_bounded_evidence(
            output_dir / "checks" / outcome.evidence_name,
            outcome.evidence,
            limits["max_evidence_file_bytes"],
        )

    schema_path = root / SCHEMA_PATH
    checks = [
        {
            "check_id": outcome.check_id,
            "title": outcome.title,
            "input_sha256": outcome.input_sha256,
            "conclusion": outcome.conclusion,
            "evidence_path": f"checks/{outcome.evidence_name}",
        }
        for outcome in outcomes
    ]
    checks.append(
        {
            "check_id": "review.report-contract",
            "title": "Review report contract self-validation",
            "input_sha256": _digest_file(schema_path),
            "conclusion": "passed",
            "evidence_path": "checks/report-contract.json",
        }
    )
    status = (
        "passed"
        if not findings and all(item["conclusion"] == "passed" for item in checks)
        else "failed"
    )
    report: dict[str, Any] = {
        "document_kind": "axiom.automated-review.report",
        "schema_version": "0.1.0",
        "report_id": f"deterministic-review-{head_sha}",
        "repository": repository,
        "pull_request_number": pull_request_number,
        "base_sha": base_sha,
        "reviewed_head_sha": head_sha,
        "generated_at": generated_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reviewer_class": "deterministic",
        "status": status,
        "findings": findings,
        "checks": checks,
        "known_unreviewed": [
            {
                "code": "semantic-intent",
                "title": "Program semantics and product intent",
                "explanation": "The deterministic gate verifies recorded contracts and "
                "evidence; it does not judge algorithmic correctness or product decisions.",
            },
            {
                "code": "advisory-ai",
                "title": "Advisory AI review",
                "explanation": "No advisory AI reviewer executed; issue #37 governs that lane.",
            },
        ],
        "unavailable": [],
        "semantic_sha256": "0" * 64,
    }
    report["semantic_sha256"] = semantic_sha256(report)

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateInternalError(f"report schema is unreadable: {error}") from error
    validation = validate_report(report, schema)
    if validation:
        codes = ", ".join(item.code for item in validation)
        raise GateInternalError(f"generated report failed contract validation: {codes}")
    summary = render_markdown(report)

    report_text = canonical_json(report)
    if len(report_text.encode("utf-8")) > limits["max_report_bytes"]:
        raise GateInternalError("review report exceeds the policy size limit")
    if len(summary.encode("utf-8")) > limits["max_summary_bytes"]:
        raise GateInternalError("review summary exceeds the policy size limit")

    _write_bounded_evidence(
        output_dir / "checks" / "report-contract.json",
        {"schema": SCHEMA_PATH.as_posix(), "validated": True, "status": status},
        limits["max_evidence_file_bytes"],
    )
    report_path = output_dir / "review-report.json"
    summary_path = output_dir / "review-summary.md"
    report_path.write_text(report_text, encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")

    exit_code = EXIT_PASSED if status == "passed" else EXIT_BLOCKED
    return GateResult(report, summary, exit_code, report_path, summary_path)
