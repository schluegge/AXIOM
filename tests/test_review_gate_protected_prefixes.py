from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from axiom_review.gate import check_protected_baseline


class ProtectedDirectoryBaselineTests(unittest.TestCase):
    def test_existing_protected_directory_prefix_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="axiom-protected-prefix-") as directory:
            root = Path(directory)
            (root / "axiom_contract").mkdir()
            policy = {"protected_paths": ["axiom_contract/"]}

            outcome = check_protected_baseline(root, policy, [])

        self.assertEqual(outcome.conclusion, "passed")
        self.assertEqual(outcome.evidence["missing"], [])
        self.assertEqual(outcome.findings, [])

    def test_missing_protected_directory_prefix_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="axiom-protected-prefix-") as directory:
            root = Path(directory)
            policy = {"protected_paths": ["axiom_contract/"]}

            outcome = check_protected_baseline(root, policy, [])

        self.assertEqual(outcome.conclusion, "failed")
        self.assertEqual(outcome.evidence["missing"], ["axiom_contract/"])
        self.assertEqual([finding["code"] for finding in outcome.findings], ["AX-REV-GATE-0401"])

    def test_exact_protected_file_still_requires_a_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="axiom-protected-file-") as directory:
            root = Path(directory)
            (root / "axiom_review").mkdir()
            (root / "axiom_review" / "gate.py").mkdir()
            policy = {"protected_paths": ["axiom_review/gate.py"]}

            outcome = check_protected_baseline(root, policy, [])

        self.assertEqual(outcome.conclusion, "failed")
        self.assertEqual(outcome.evidence["missing"], ["axiom_review/gate.py"])


if __name__ == "__main__":
    unittest.main()
