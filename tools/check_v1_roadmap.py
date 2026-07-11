from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "roadmap" / "v1.json"


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"AX-ROADMAP-0001 missing contract: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"AX-ROADMAP-0002 invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise SystemExit("AX-ROADMAP-0003 contract root must be an object")
    return value


def validate_local(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    if contract.get("schema_version") != "1.0.0":
        findings.append(Finding("AX-ROADMAP-0004", "schema_version must be 1.0.0"))
    if contract.get("release") != "v1.0.0":
        findings.append(Finding("AX-ROADMAP-0005", "release must be v1.0.0"))
    if contract.get("program_issue") != 9:
        findings.append(Finding("AX-ROADMAP-0006", "program_issue must be #9"))
    if contract.get("release_gate_issue") != 25:
        findings.append(Finding("AX-ROADMAP-0007", "release_gate_issue must be #25"))

    milestones = contract.get("milestones")
    if not isinstance(milestones, list):
        return [*findings, Finding("AX-ROADMAP-0008", "milestones must be an array")]

    expected_ids = [f"M{i}" for i in range(14)]
    actual_ids = [item.get("id") for item in milestones if isinstance(item, dict)]
    if actual_ids != expected_ids:
        findings.append(
            Finding("AX-ROADMAP-0009", f"milestone order must be {expected_ids}; got {actual_ids}")
        )

    issue_numbers: list[int] = []
    for index, item in enumerate(milestones):
        if not isinstance(item, dict):
            findings.append(Finding("AX-ROADMAP-0010", f"milestone {index} must be an object"))
            continue
        milestone_id = f"M{index}"
        if item.get("id") != milestone_id:
            findings.append(Finding("AX-ROADMAP-0011", f"position {index} must contain {milestone_id}"))
        issue = item.get("issue")
        if not isinstance(issue, int) or issue < 1:
            findings.append(Finding("AX-ROADMAP-0012", f"{milestone_id} has invalid issue number"))
        else:
            issue_numbers.append(issue)
        expected_dependency = None if index == 0 else f"M{index - 1}"
        if item.get("depends_on") != expected_dependency:
            findings.append(
                Finding(
                    "AX-ROADMAP-0013",
                    f"{milestone_id} must depend on {expected_dependency!r}",
                )
            )
        expected_next = "V1" if index == 13 else f"M{index + 1}"
        if item.get("next") != expected_next:
            findings.append(
                Finding("AX-ROADMAP-0014", f"{milestone_id} must point to {expected_next}")
            )
        expected_prefix = f"{milestone_id}:"
        if item.get("title_prefix") != expected_prefix:
            findings.append(
                Finding("AX-ROADMAP-0015", f"{milestone_id} title_prefix must be {expected_prefix!r}")
            )
        status = item.get("status")
        if status not in {"blocked", "active", "complete"}:
            findings.append(Finding("AX-ROADMAP-0016", f"{milestone_id} has invalid status {status!r}"))

    if len(issue_numbers) != len(set(issue_numbers)):
        findings.append(Finding("AX-ROADMAP-0017", "milestone issue numbers must be unique"))

    active = [
        item.get("id")
        for item in milestones
        if isinstance(item, dict) and item.get("status") == "active"
    ]
    if active != [contract.get("active_milestone")]:
        findings.append(
            Finding(
                "AX-ROADMAP-0018",
                f"exactly active_milestone={contract.get('active_milestone')!r} must be active; got {active}",
            )
        )

    seen_incomplete = False
    for item in milestones:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status != "complete":
            seen_incomplete = True
        elif seen_incomplete:
            findings.append(
                Finding("AX-ROADMAP-0019", f"{item.get('id')} cannot be complete before an earlier milestone")
            )

    gate = contract.get("release_gate")
    if not isinstance(gate, dict):
        findings.append(Finding("AX-ROADMAP-0020", "release_gate must be an object"))
    else:
        if gate.get("id") != "V1" or gate.get("depends_on") != "M13":
            findings.append(Finding("AX-ROADMAP-0021", "release gate must be V1 depending on M13"))
        if gate.get("issue") != contract.get("release_gate_issue"):
            findings.append(
                Finding("AX-ROADMAP-0022", "release_gate.issue must equal release_gate_issue")
            )
        if gate.get("issue") in issue_numbers:
            findings.append(Finding("AX-ROADMAP-0023", "release gate issue must be distinct"))
        if gate.get("status") not in {"blocked", "active", "complete"}:
            findings.append(Finding("AX-ROADMAP-0024", "release gate status is invalid"))
        if gate.get("title_prefix") != "AXIOM v1.0 release gate:":
            findings.append(Finding("AX-ROADMAP-0025", "release gate title prefix is not canonical"))

    program_issue = contract.get("program_issue")
    if program_issue in issue_numbers or program_issue == contract.get("release_gate_issue"):
        findings.append(Finding("AX-ROADMAP-0026", "program issue must be distinct from tracked work"))

    post_v1 = contract.get("post_v1_issues")
    if not isinstance(post_v1, list) or not all(
        isinstance(number, int) and number > 0 for number in post_v1
    ):
        findings.append(Finding("AX-ROADMAP-0027", "post_v1_issues must contain positive integers"))
    elif set(post_v1) & (set(issue_numbers) | {program_issue, contract.get("release_gate_issue")}):
        findings.append(Finding("AX-ROADMAP-0028", "post-v1 issues may not overlap the v1 graph"))

    documents = contract.get("canonical_documents")
    if not isinstance(documents, list) or not documents:
        findings.append(Finding("AX-ROADMAP-0029", "canonical_documents must be a non-empty array"))
    else:
        for relative in documents:
            if not isinstance(relative, str) or not relative:
                findings.append(Finding("AX-ROADMAP-0030", "canonical document paths must be strings"))
                continue
            if not (ROOT / relative).is_file():
                findings.append(Finding("AX-ROADMAP-0031", f"missing canonical document: {relative}"))

    required_repository_files = [
        "roadmap/v1.schema.json",
        "V1_TRACKING.md",
        ".github/ISSUE_TEMPLATE/axiom-capability.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/pull_request_template.md",
        ".github/workflows/v1-roadmap-contract.yml",
        "tools/check_v1_roadmap.py",
    ]
    for relative in required_repository_files:
        if not (ROOT / relative).is_file():
            findings.append(Finding("AX-ROADMAP-0032", f"missing tracking control: {relative}"))

    return findings


def github_issue(repository: str, issue_number: int, token: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repository}/issues/{issue_number}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "axiom-v1-roadmap-checker",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub issue #{issue_number} returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub issue #{issue_number} could not be read: {exc.reason}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"GitHub issue #{issue_number} returned a non-object")
    return value


def issue_logins(issue: dict[str, Any]) -> set[str]:
    return {
        str(entry.get("login"))
        for entry in issue.get("assignees", [])
        if isinstance(entry, dict) and entry.get("login")
    }


def issue_labels(issue: dict[str, Any]) -> set[str]:
    return {
        str(entry.get("name"))
        for entry in issue.get("labels", [])
        if isinstance(entry, dict) and entry.get("name")
    }


def validate_github(contract: dict[str, Any], repository: str, token: str) -> list[Finding]:
    findings: list[Finding] = []
    milestones = contract["milestones"]
    issues_by_number: dict[int, dict[str, Any]] = {}
    tracked = [
        contract["program_issue"],
        *(item["issue"] for item in milestones),
        contract["release_gate_issue"],
    ]
    for issue_number in tracked:
        try:
            issues_by_number[issue_number] = github_issue(repository, issue_number, token)
        except RuntimeError as exc:
            findings.append(Finding("AX-ROADMAP-0100", str(exc)))

    if findings:
        return findings

    program = issues_by_number[contract["program_issue"]]
    release = issues_by_number[contract["release_gate_issue"]]
    program_body = program.get("body") or ""
    release_body = release.get("body") or ""

    if not str(program.get("title", "")).startswith("AXIOM v1.0 program:"):
        findings.append(Finding("AX-ROADMAP-0101", "program issue title is not canonical"))
    if program.get("state") != "open":
        findings.append(Finding("AX-ROADMAP-0102", "program issue must remain open until v1 completion"))
    if "schluegge" not in issue_logins(program):
        findings.append(Finding("AX-ROADMAP-0103", "program issue must be assigned to schluegge"))
    if "enhancement" not in issue_labels(program):
        findings.append(Finding("AX-ROADMAP-0104", "program issue must carry enhancement label"))

    gate = contract["release_gate"]
    if not str(release.get("title", "")).startswith(gate["title_prefix"]):
        findings.append(Finding("AX-ROADMAP-0105", "release gate issue title is not canonical"))
    expected_release_state = "closed" if gate["status"] == "complete" else "open"
    if release.get("state") != expected_release_state:
        findings.append(
            Finding("AX-ROADMAP-0106", "release issue state conflicts with roadmap contract")
        )
    if "schluegge" not in issue_logins(release):
        findings.append(Finding("AX-ROADMAP-0107", "release gate must be assigned to schluegge"))
    if "enhancement" not in issue_labels(release):
        findings.append(Finding("AX-ROADMAP-0108", "release gate must carry enhancement label"))
    if "Depends on: #24" not in release_body:
        findings.append(Finding("AX-ROADMAP-0109", "release gate must depend on #24"))

    prior_closed = True
    previous_issue_number: int | None = None
    for item in milestones:
        issue_number = item["issue"]
        issue = issues_by_number[issue_number]
        title = str(issue.get("title", ""))
        body = issue.get("body") or ""
        state = issue.get("state")
        if not title.startswith(item["title_prefix"]):
            findings.append(
                Finding("AX-ROADMAP-0110", f"issue #{issue_number} title must start with {item['title_prefix']!r}")
            )
        if "Parent: #9" not in body:
            findings.append(Finding("AX-ROADMAP-0111", f"issue #{issue_number} must declare Parent: #9"))
        if "Target release: AXIOM v1.0" not in body:
            findings.append(
                Finding("AX-ROADMAP-0112", f"issue #{issue_number} must declare the v1 target")
            )
        if "Canonical specification:" not in body:
            findings.append(
                Finding("AX-ROADMAP-0113", f"issue #{issue_number} must name its canonical specification")
            )
        if previous_issue_number is not None and f"Depends on: #{previous_issue_number}" not in body:
            findings.append(
                Finding(
                    "AX-ROADMAP-0114",
                    f"issue #{issue_number} must declare dependency on #{previous_issue_number}",
                )
            )
        if "schluegge" not in issue_logins(issue):
            findings.append(Finding("AX-ROADMAP-0115", f"issue #{issue_number} must be assigned to schluegge"))
        if "enhancement" not in issue_labels(issue):
            findings.append(Finding("AX-ROADMAP-0116", f"issue #{issue_number} must carry enhancement label"))
        expected_state = "closed" if item["status"] == "complete" else "open"
        if state != expected_state:
            findings.append(
                Finding(
                    "AX-ROADMAP-0117",
                    f"issue #{issue_number} state {state!r} conflicts with contract status {item['status']!r}",
                )
            )
        if state == "closed" and not prior_closed:
            findings.append(Finding("AX-ROADMAP-0118", f"issue #{issue_number} closed before its dependency"))
        prior_closed = prior_closed and state == "closed"
        marker = f"#{issue_number}"
        if marker not in program_body:
            findings.append(Finding("AX-ROADMAP-0119", f"program issue does not reference {marker}"))
        if marker not in release_body:
            findings.append(Finding("AX-ROADMAP-0120", f"release gate does not reference {marker}"))
        previous_issue_number = issue_number

    return findings


def write_report(findings: list[Finding], github_checked: bool) -> None:
    report = {
        "document_kind": "axiom.v1-roadmap-check",
        "schema_version": "1.0.0",
        "status": "passed" if not findings else "failed",
        "github_checked": github_checked,
        "findings": [{"code": item.code, "message": item.message} for item in findings],
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the AXIOM v1 roadmap contract")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--github", action="store_true", help="also verify live GitHub issues")
    args = parser.parse_args(argv)

    contract = load_json(args.contract)
    findings = validate_local(contract)
    github_checked = False

    if args.github and not findings:
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        if not repository or not token:
            findings.append(
                Finding("AX-ROADMAP-0200", "--github requires GITHUB_REPOSITORY and GITHUB_TOKEN")
            )
        else:
            github_checked = True
            findings.extend(validate_github(contract, repository, token))

    write_report(findings, github_checked)
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
