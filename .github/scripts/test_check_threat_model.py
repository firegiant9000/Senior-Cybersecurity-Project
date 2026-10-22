import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path

import check_threat_model as ctm

TODAY = date(2026, 10, 22)
HEADER = "| ID | STRIDE | Threat | Class | Evidence | Notes |\n|---|---|---|---|---|---|\n"
REAL = Path(__file__).resolve().parents[2] / "docs/security/threat_model.md"

CONTROL_EV = "`src/app.py::Guard.enforce` (L2)"
TEST_EV = "`tests/test_app.py::TestGuard::test_enforced`"
ACCEPTED_EV = "reason: r; owner: Arlo; review: 2027-04-22"
OPEN_EV = "milestone: S4; item: route suite"


def row(id_="T-UPL-01", stride="T", cls="CONTROL", evidence=CONTROL_EV, notes="", threat="t"):
    return f"| {id_} | {stride} | {threat} | {cls} | {evidence} | {notes} |\n"


def doc(*rows):
    return "# Threat model\n\n" + HEADER + "".join(rows)


class CheckThreatModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        for rel, text in {
            "src/app.py": "class Guard:\n    def enforce(self): pass\n",
            "tests/test_app.py": (
                "class TestGuard:\n    def test_enforced(self): pass\n\n"
                "def test_foobar(): pass\n"
            ),
            "agent/x_test.go": "func TestScan(t *testing.T) {}",
        }.items():
            path = cls.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def check(self, text):
        return ctm.check(text, self.root, TODAY)

    def valid_doc(self):
        return doc(
            row("T-UPL-01", "T", "CONTROL", CONTROL_EV),
            row("T-UPL-02", "T", "TEST", TEST_EV),
            row("T-UPL-03", "R", "ACCEPTED", ACCEPTED_EV),
            row("T-UPL-04", "D", "OPEN", OPEN_EV),
        )

    def test_valid_rows_pass(self):
        self.assertEqual(self.check(self.valid_doc()), [])

    def test_bad_id_and_duplicate_id(self):
        problems = self.check(
            doc(row("T-XYZ-01"), row("T-UPL-01"), row("T-UPL-01"))
        )
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any("T-XYZ-01" in p for p in problems), problems)
        self.assertTrue(any("T-UPL-01" in p for p in problems), problems)

    def test_bad_stride_and_class(self):
        self.assertEqual(len(self.check(doc(row(stride="X")))), 1)
        self.assertEqual(len(self.check(doc(row(cls="MAYBE")))), 1)

    def test_control_missing_path_or_symbol(self):
        self.assertEqual(len(self.check(doc(row(evidence="`src/nope.py::f`")))), 1)
        self.assertEqual(
            len(self.check(doc(row(evidence="`src/app.py::Guard.missing`")))), 1
        )

    def test_path_outside_repo_rejected(self):
        for ev in ("`../etc/passwd::x`", "`/etc/passwd::x`", "`C:/x.py::y`"):
            with self.subTest(ev=ev):
                problems = self.check(doc(row(evidence=ev)))
                self.assertEqual(len(problems), 1, problems)
                self.assertIn("outside repo", problems[0])
        problems = self.check(doc(row(cls="TEST", evidence="`a/../../x.py::test_x`")))
        self.assertTrue(any("outside repo" in p for p in problems), problems)

    def test_test_name_prefix_does_not_match(self):
        bad = self.check(doc(row(cls="TEST", evidence="`tests/test_app.py::test_foo`")))
        self.assertEqual(len(bad), 1, bad)
        ok = self.check(doc(row(cls="TEST", evidence="`tests/test_app.py::test_foobar`")))
        self.assertEqual(ok, [])

    def test_go_test_found(self):
        self.assertEqual(
            self.check(doc(row(cls="TEST", evidence="`agent/x_test.go::TestScan`"))), []
        )

    def test_test_missing_class(self):
        problems = self.check(
            doc(row(cls="TEST", evidence="`tests/test_app.py::TestNope::test_enforced`"))
        )
        self.assertEqual(len(problems), 1, problems)

    def test_mock_guard(self):
        problems = self.check(doc(row("T-TEN-01", cls="TEST", evidence=TEST_EV)))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("real-verification", problems[0])
        ok = self.check(
            doc(row("T-TEN-01", cls="TEST", evidence=TEST_EV, notes="real-verification: db"))
        )
        self.assertEqual(ok, [])

    def test_review_today_ok_yesterday_fails(self):
        ok = self.check(
            doc(row(cls="ACCEPTED", evidence="reason: r; owner: A; review: 2026-10-22"))
        )
        self.assertEqual(ok, [])
        bad = self.check(
            doc(row(cls="ACCEPTED", evidence="reason: r; owner: A; review: 2026-10-21"))
        )
        self.assertEqual(len(bad), 1, bad)
        self.assertIn("has passed", bad[0])

    def test_accepted_missing_fields(self):
        problems = self.check(
            doc(row(cls="ACCEPTED", evidence="reason: r; review: 2027-04-22"))
        )
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("owner", problems[0])

    def test_open_bad_milestone(self):
        problems = self.check(
            doc(row(cls="OPEN", evidence="milestone: S9; item: x"))
        )
        self.assertEqual(len(problems), 1, problems)

    def test_withdrawn_skips_evidence(self):
        self.assertEqual(
            self.check(doc(row(evidence="", notes="withdrawn: dup of T-UPL-02"))), []
        )

    def test_wrong_cell_count_is_reported(self):
        text = doc(row()) + "| T-UPL-02 | T | a | b | CONTROL | e | n |\n"
        problems = self.check(text)
        self.assertTrue(any("cells" in p for p in problems), problems)

    def test_crlf_and_no_trailing_pipe_parse(self):
        # Notes must be non-empty: with the trailing pipe gone, an empty last cell is
        # indistinguishable from a missing one.
        lines = self.valid_doc().replace("|  |\n", "| n |\n").splitlines()
        text = "\r\n".join(line.rstrip("|") for line in lines) + "\r\n"
        self.assertEqual(self.check(text), [])

    def test_no_tables_is_error(self):
        problems = self.check("# empty\n")
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("no threat tables", problems[0])

    def test_main_exit_codes(self):
        good = self.root / "good.md"
        good.write_text(self.valid_doc(), encoding="utf-8")
        bad = self.root / "bad.md"
        bad.write_text(doc(row(stride="X")), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ctm.main([str(good), "--repo-root", str(self.root)]), 0)
        self.assertIn("threat model OK: 4 threats", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ctm.main([str(bad), "--repo-root", str(self.root)]), 1)
        self.assertIn("::error::", out.getvalue())

    @unittest.skipUnless(REAL.exists(), "docs/security/threat_model.md not written yet")
    def test_real_threat_model(self):
        today = datetime.now(timezone.utc).date()
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(ctm.check(REAL.read_text(encoding="utf-8"), root, today), [])


if __name__ == "__main__":
    unittest.main()
