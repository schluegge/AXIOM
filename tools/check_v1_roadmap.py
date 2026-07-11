from __future__ import annotations

import argparse
import json
import os
import sys
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
    milestones = contract.get("milestones")
    if not isinstance(milestones, list):
        return [Finding("AX-ROADMAP-0004", "milestones must be an array")]

    expected_ids = [f"M{i}" for i in range(14)]
    actual_ids = [item.get("id") for item in milestones if isinstance(item, dict)]
    if actual_ids != expected_ids:
        findings.append(
            Finding("AX-ROADMAP-0005", f"milestone order must be {expected_ids}; got {actual_ids}")
        )

    issue_numbers: list[int] = []
    statuses: list[str] = []
    for index, item in enumerate(milestones):
        if not isinstance(item, dict):
            findings.append(Finding("AX-ROADMAP-0006", f"milestone {index} must be an object"))
            continue
        milestone_id = f"M{index}"
        issue = item.get("issue")
        if not isinstance(issue, int) or issue < 1:
            findings.append(Finding("AX-ROADMAP-0007", f"{milestone_id} has invalid issue number"))
        else:
            issue_numbers.append(issue)
        expected_dependency = None if index == 0 else f"M{index - 1}"
        if item.get("depends_on") != expected_dependency:
            findings.append(
                Finding(
                    "AX-ROADMAP-0008",
                    f"{milestone_id} must depend on {expected_dependency!r}",
                )
            )
        expected_next = "V1" if index == 13 else f"M{index + 1}"
        if item.get("next") != expected_next:
            findings.append(
                Finding("AX-ROADMAP-0009", f"{milestone_id} must point to {expected_next}")
            )
        expected_prefix = f"{milestone_id}:"
        if item.get("title_prefix") != expected_prefix:
            findings.append(
                Finding("AX-ROADMAP-0010", f"{milestone_id} title_prefix must be {expected_prefix!r}")
            )
        status = item.get("status")
        if status not in {"blocked", "active", "complete"}:
            findings.append(Finding("AX-ROADMAP-0011", f"{milestone_id} has invalid status {status!r}"))
        else:
            statuses.append(status)

    if len(issue_numbers) != len(set(issue_numbers)):
        findings.append(Finding("AX-ROADMAP-0012", "milestone issue numbers must be unique"))

    active = [item.get("id") for item in milestones if isinstance(item, dict) and item.get("status") == "active"]
    if active != [contract.get("active_milestone")]:
        findings.append(
            Finding(
                "AX-ROADMAP-0013",
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
                Finding("AX-ROADMAP-0014", f"{item.get('id')} cannot be complete before an earlier milestone")
            )

    gate = contract.get("release_gate")
    if not isinstance(gate, dict):
        findings.append(Finding("AX-ROADMAP-0015", "release_gate must be an object"))
    else:
        if gate.get("id") != "V1" or gate.get("depends_on") != "M13":
            findings.append(Finding("AX-ROADMAP-0016", "release gate must be V1 depending on M13"))
        if gate.get("issue") != contract.get("release_gate_issue"):
            findings.append(
                Finding("AX-ROADMAP-0017", "release_gate.issue must equal release_gate_issue")
            )
        if gate.get("issue") in issue_numbers:
            findings.append(Finding("AX-ROADMAP-0018", "release gate issue must be distinct"))

    program_issue = contract.get("program_issue")
    if program_issue in issue_numbers or program_issue == contract.get("release_gate_issue"):
        findings.append(Finding("AX-ROADMAP-0019", "program issue must be distinct from tracked work"))

    post_v1 = contract.get("post_v1_issues")
    if not isinstance(post_v1, list) or not all(isinstance(number, int) and number > 0 for number in post_v1):
        findings.append(Finding("AX-ROADMAP-0020", "post_v1_issues must contain positive integers"))
    elif set(post_v1) & (set(issue_numbers) | {program_issue, contract.get("release_gate_issue")}):
        findings.append(Finding("AX-ROADMAP-0021", "post-v1 issues may not overlap the v1 graph"))

    documents = contract.get("canonical_documents")
    if not isinstance(documents, list) or not documents:
        findings.append(Finding("AX-ROADMAP-0022", "canonical_documents must be a non-empty array"))
    else:
        for relative in documents:
            if not isinstance(relative, str) or not relative:
                findings.append(Finding("AX-ROADMAP-0023", "canonical document paths must be strings"))
                continue
            if not (ROOT / relative).is_file():
                findings.append(Finding("AX-ROADMAP-0024", f"missing canonical document: {relative}"))

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


def validate_github(contract: dict[str, Any], repository: str, token: str) -> list[Finding]:
    findings: list[Finding] = []
    milestones = contract["milestones"]
    issues_by_number: dict[int, dict[str, Any]] = {}
    tracked = [contract["program_issue"], *(item["issue"] for item in milestones), contract["release_gate_issue"]]
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
    if not str(release.get("title", "")).startswith(contract["release_gate"]["title_prefix"]):
        findings.append(Finding("AX-ROADMAP-0102", "release gate issue title is not canonical"))

    prior_closed = True
    for item in milestones:
        issue_number = item["issue"]
        issue = issues_by_number[issue_number]
        title = str(issue.get("title", ""))
        body = issue.get("body") or ""
        state = issue.get("state")
        if not title.startswith(item["title_prefix"]):
            findings.append(
                Finding("AX-ROADMAP-0103", f"issue #{issue_number} title must start with {item['title_prefix']!r}")
            )
        if "Parent: #9" not in body:
            findings.append(Finding("AX-ROADMAP-0104", f"issue #{issue_number} must declare Parent: #9"))
        if "Target release: AXIOM v1.0" not in body:
            findings.append(
                Finding("AX-ROADMAP-0105", f"issue #{issue_number} must declare the v1 target")
            )
        assignees = {entry.get("login") for entry in issue.get("assignees", []) if isinstance(entry, dict)}
        if "schluegge" not in assignees:
            findings.append(Finding("AX-ROADMAP-0106", f"issue #{issue_number} must be assigned to schluegge"))
        expected_state = "closed" if item["status"] == "complete" else "open"
        if state != expected_state:
            findings.append(
                Finding(
                    "AX-ROADMAP-0107",
                    f"issue #{issue_number} state {state!r} conflicts with contract status {item['status']!r}",
                )
            )
        if state == "closed" and not prior_closed:
            findings.append(Finding("AX-ROADMAP-0108", f"issue #{issue_number} closed before its dependency"))
        prior_closed = prior_closed and state == "closed"
        marker = f"#{issue_number}"
        if marker not in program_body:
            findings.append(Finding("AX-ROADMAP-0109", f"program issue does not reference {marker}"))
        if marker not in release_body:
            findings.append(Finding("AX-ROADMAP-0110", f"release gate does not reference {marker}"))

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
