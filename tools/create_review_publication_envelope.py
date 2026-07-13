from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from axiom_review.contract import canonical_json  # noqa: E402
from axiom_review.gate import GateInputError, load_event  # noqa: E402
from axiom_review.publisher import (  # noqa: E402
    PublicationIdentity,
    PublicationRejected,
    create_publication_envelope,
)

MAX_REPORT_BYTES = 1_048_576
MAX_SUMMARY_BYTES = 262_144


def _read_bounded(path: Path, limit: int, label: str) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise PublicationRejected(f"{label} could not be inspected: {path}: {error}") from error
    if size > limit:
        raise PublicationRejected(f"{label} exceeds byte limit: {size} > {limit}")
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise PublicationRejected(f"{label} could not be read: {path}: {error}") from error
    if len(payload) != size:
        raise PublicationRejected(f"{label} changed while it was read: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bind one deterministic review report to its workflow-run identity"
    )
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--workflow-run-url", required=True)
    parser.add_argument("--artifact-name", required=True)
    args = parser.parse_args(argv)

    try:
        event_identity = load_event(args.event)
        identity = PublicationIdentity(
            repository=event_identity["repository"],
            pull_request_number=event_identity["pull_request_number"],
            base_sha=event_identity["base_sha"],
            reviewed_head_sha=event_identity["head_sha"],
            workflow_run_id=args.workflow_run_id,
            workflow_run_attempt=args.workflow_run_attempt,
            workflow_name=args.workflow_name,
            workflow_run_url=args.workflow_run_url,
            artifact_name=args.artifact_name,
        )
        if identity.workflow_run_id < 1 or identity.workflow_run_attempt < 1:
            raise PublicationRejected("workflow run identity must be positive")
        report_bytes = _read_bounded(args.report, MAX_REPORT_BYTES, "review report")
        summary_bytes = _read_bounded(args.summary, MAX_SUMMARY_BYTES, "review summary")
        envelope = create_publication_envelope(identity, report_bytes, summary_bytes)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(canonical_json(envelope), encoding="utf-8")
    except (GateInputError, PublicationRejected, OSError) as error:
        print(f"publication envelope failed closed: {error}", file=sys.stderr)
        return 2

    print(canonical_json({"status": "passed", "output": str(args.output)}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
