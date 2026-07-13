from __future__ import annotations

import unittest

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

    def test_pull_request_file_listing_is_paginated_and_bounded(self) -> None:
        calls: list[str] = []

        def transport(method, url, headers, body, max_bytes, follow_redirects):
            calls.append(url)
            if "page=1" in url:
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


if __name__ == "__main__":
    unittest.main()
