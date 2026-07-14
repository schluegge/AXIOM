from __future__ import annotations

import json
import unittest
from pathlib import Path

from axiom_review.publisher import (
    GitHubRestApi,
    HttpResponse,
    PublicationRejected,
    ensure_trusted_gate_inputs_unchanged,
)


class TrustedGateInputTests(unittest.TestCase):
    def test_protected_gate_change_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            PublicationRejected,
            "protected deterministic-review input changed",
        ):
            ensure_trusted_gate_inputs_unchanged(
                ["src/example.py", "tools/run_deterministic_review.py"],
                ["tools/run_deterministic_review.py", "review/policy/0.1.0/gate-policy.json"],
            )

    def test_unprotected_change_is_allowed(self) -> None:
        ensure_trusted_gate_inputs_unchanged(
            ["src/example.py", "docs/example.md"],
            ["tools/run_deterministic_review.py", "review/policy/0.1.0/gate-policy.json"],
        )

    def test_gate_implementation_is_protected(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = json.loads(
            (root / "review/policy/0.1.0/gate-policy.json").read_text(encoding="utf-8")
        )
        self.assertIn("axiom_review/gate.py", policy["protected_paths"])
        self.assertIn("axiom_review/contract.py", policy["protected_paths"])

    def test_pull_request_file_listing_is_paginated_and_bounded(self) -> None:
        calls: list[str] = []

        def transport(method, url, headers, body, max_bytes, follow_redirects):
            calls.append(url)
            if url.endswith("page=1"):
                payload = b"[" + b",".join(
                    b'{"filename":"src/file-' + str(index).encode("ascii") + b'.py"}'
                    for index in range(100)
                ) + b"]"
                return HttpResponse(200, {}, payload)
            return HttpResponse(200, {}, b'[{"filename":"docs/final.md"}]')

        api = GitHubRestApi("token", transport=transport)
        files = api.list_pull_request_files("schluegge/AXIOM", 35)

        self.assertEqual(len(files), 101)
        self.assertEqual(files[-1]["filename"], "docs/final.md")
        self.assertTrue(calls[0].endswith("/repos/schluegge/AXIOM/pulls/35/files?per_page=100&page=1"))
        self.assertTrue(calls[1].endswith("/repos/schluegge/AXIOM/pulls/35/files?per_page=100&page=2"))

    def test_reviewed_commit_diff_uses_exact_base_and_head(self) -> None:
        calls: list[str] = []
        base_sha = "1" * 40
        head_sha = "2" * 40

        def transport(method, url, headers, body, max_bytes, follow_redirects):
            calls.append(url)
            return HttpResponse(
                200,
                {},
                b'{"status":"ahead","files":[{"filename":"axiom_review/gate.py"}]}',
            )

        api = GitHubRestApi("token", transport=transport)
        files = api.list_compare_files("schluegge/AXIOM", base_sha, head_sha)

        self.assertEqual(files, [{"filename": "axiom_review/gate.py"}])
        self.assertTrue(
            calls[0].endswith(
                f"/repos/schluegge/AXIOM/compare/{base_sha}...{head_sha}"
            )
        )

    def test_reviewed_commit_diff_rejects_possible_file_truncation(self) -> None:
        payload = json.dumps(
            {"status": "ahead", "files": [{"filename": f"src/{index}.py"} for index in range(300)]}
        ).encode("utf-8")

        def transport(method, url, headers, body, max_bytes, follow_redirects):
            return HttpResponse(200, {}, payload)

        api = GitHubRestApi("token", transport=transport)
        with self.assertRaisesRegex(PublicationRejected, "compare file list reached limit"):
            api.list_compare_files("schluegge/AXIOM", "1" * 40, "2" * 40)


if __name__ == "__main__":
    unittest.main()
