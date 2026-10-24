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
            "tests/test_collect.py": (
                "def helper(): pass\n\n"
                "def test_top(): pass\n\n"
                "async def test_async_top(): pass\n\n"
                "def outer():\n    def test_nested_fn(): pass\n\n"
                "class Fake:\n    def test_in_fake(self): pass\n\n"
                "class TestReal:\n"
                "    def test_method(self): pass\n\n"
                "    def helper_method(self): pass\n\n"
                "    def test_with_inner(self):\n        def test_inner(): pass\n\n"
                "class UnitStyle(unittest.TestCase):\n    def test_u(self): pass\n"
            ),
            "agent/y_test.go": (
                "func helper() {}\n"
                "func TestOk(t *testing.T) {}\n"
                "func Testlower(t *testing.T) {}\n"
                "func TestOuter() {\n\tfunc TestInner() {}\n}\n"
            ),
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
        self.assertEqual(len(self.check(doc(row(evidence="`src/nope.py::f` (L1)")))), 1)
        self.assertEqual(
            len(self.check(doc(row(evidence="`src/app.py::Guard.missing` (L1)")))), 1
        )

    def test_path_outside_repo_rejected(self):
        for ev in ("`../etc/passwd::x` (L1)", "`/etc/passwd::x` (L1)", "`C:/x.py::y` (L1)"):
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

    def accepted(self, ev):
        return self.check(doc(row(cls="ACCEPTED", evidence=ev)))

    def test_near_miss_header_is_reported(self):
        text = "| ID | Stride | Threat | Class | Evidence | Notes |\n|---|---|---|---|---|---|\n" + row()
        problems = self.check(text)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("header must be exactly", problems[0])
        self.assertTrue(problems[0].startswith("line 1:"), problems)

    def test_control_requires_line_hint(self):
        problems = self.check(doc(row(evidence="`src/app.py::Guard.enforce`")))
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("(L", problems[0])

    def test_symbol_matches_whole_identifier(self):
        problems = self.check(doc(row(evidence="`src/app.py::Guard.enfor` (L2)")))
        self.assertEqual(len(problems), 1, problems)
        problems = self.check(doc(row(evidence="`src/app.py::Gua.enforce` (L2)")))
        self.assertEqual(len(problems), 1, problems)

    def test_test_def_must_be_inside_class(self):
        problems = self.check(
            doc(row(cls="TEST", evidence="`tests/test_app.py::TestGuard::test_foobar`"))
        )
        self.assertEqual(len(problems), 1, problems)

    def test_test_path_must_be_test_file(self):
        problems = self.check(doc(row(cls="TEST", evidence="`src/app.py::enforce`")))
        self.assertTrue(any("not a test file" in p for p in problems), problems)

    def test_empty_evidence_for_control_and_test(self):
        p = self.check(doc(row(evidence="")))
        self.assertEqual(len(p), 1, p)
        self.assertIn("CONTROL needs evidence", p[0])
        p = self.check(doc(row(cls="TEST", evidence="see tests")))
        self.assertEqual(len(p), 1, p)
        self.assertIn("TEST needs evidence", p[0])

    def test_degenerate_symbols_do_not_crash(self):
        for cls in ("TEST", "CONTROL"):
            p = self.check(doc(row(cls=cls, evidence="`tests/test_app.py::::`")))
            self.assertTrue(p, p)

    def test_mock_guard_marker_is_token_and_auth_id(self):
        p = self.check(doc(row("T-AUTH-01", cls="TEST", evidence=TEST_EV)))
        self.assertEqual(len(p), 1, p)
        p = self.check(
            doc(row("T-AUTH-01", cls="TEST", evidence=TEST_EV, notes="no real-verification"))
        )
        self.assertEqual(len(p), 1, p)
        ok = self.check(
            doc(row("T-AUTH-01", cls="TEST", evidence=TEST_EV, notes="x; real-verification: db"))
        )
        self.assertEqual(ok, [])

    def test_fenced_blocks_are_skipped(self):
        text = self.valid_doc() + "\n```\n" + HEADER + "| bad |\n```\n"
        self.assertEqual(self.check(text), [])

    def test_review_too_far_out(self):
        p = self.accepted("reason: r; owner: A; review: 2027-10-24")
        self.assertEqual(len(p), 1, p)
        self.assertIn("more than 365 days", p[0])
        self.assertEqual(self.accepted("reason: r; owner: A; review: 2027-10-22"), [])

    def test_review_date_boundary_and_invalid(self):
        self.assertEqual(len(self.accepted("reason: r; owner: A; review: 2027-04-221")), 1)
        p = self.accepted("reason: r; owner: A; review: 2026-02-30")
        self.assertEqual(len(p), 1, p)
        self.assertIn("2026-02-30", p[0])

    def test_accepted_missing_reason_and_review(self):
        p = self.accepted("owner: A; review: 2027-04-22")
        self.assertEqual(len(p), 1, p)
        self.assertIn("reason", p[0])
        p = self.accepted("reason: r; owner: A")
        self.assertEqual(len(p), 1, p)
        self.assertIn("review", p[0])

    def test_keys_need_left_word_boundary(self):
        self.assertEqual(len(self.accepted("xreason: r; owner: A; review: 2027-04-22")), 1)
        p = self.check(doc(row(cls="OPEN", evidence="milestone: S4; subitem: x")))
        self.assertEqual(len(p), 1, p)
        self.assertIn("item", p[0])

    def test_open_missing_item(self):
        p = self.check(doc(row(cls="OPEN", evidence="milestone: S4")))
        self.assertEqual(len(p), 1, p)

    def test_withdrawn_still_checks_id(self):
        p = self.check(doc(row("T-BAD-01", notes="withdrawn: dup")))
        self.assertEqual(len(p), 1, p)
        self.assertIn("T-BAD-01", p[0])

    def test_withdrawn_needs_reason(self):
        p = self.check(doc(row(evidence="", notes="withdrawn:")))
        self.assertEqual(len(p), 1, p)

    def test_empty_id_uses_line_label(self):
        p = self.check(doc(row("")))
        self.assertTrue(p and all(x.startswith("line ") for x in p), p)

    def test_ok_line_reports_withdrawn_separately(self):
        text = self.valid_doc() + row("T-UPL-05", evidence="", notes="withdrawn: dup")
        path = self.root / "w.md"
        path.write_text(text, encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ctm.main([str(path), "--repo-root", str(self.root)]), 0)
        self.assertIn("4 threats", out.getvalue())
        self.assertIn("1 withdrawn", out.getvalue())

    def test_cited_test_must_be_collectable(self):
        good = (
            "tests/test_collect.py::test_top",
            "tests/test_collect.py::test_async_top",
            "tests/test_collect.py::TestReal::test_method",
            "tests/test_collect.py::UnitStyle::test_u",
            "agent/y_test.go::TestOk",
        )
        for ev in good:
            with self.subTest(ev=ev):
                self.assertEqual(self.check(doc(row(cls="TEST", evidence=f"`{ev}`"))), [])
        bad = (
            "tests/test_collect.py::helper",  # not named test*
            "tests/test_collect.py::test_nested_fn",  # nested helper, not column 0
            "tests/test_collect.py::Fake::test_in_fake",  # class is not Test*
            "tests/test_collect.py::TestReal::helper_method",  # not named test*
            "tests/test_collect.py::TestReal::test_inner",  # nested deeper than class body
            "tests/test_collect.py::TestReal::test_top",  # module-level function, not a method
            "agent/y_test.go::helper",
            "agent/y_test.go::Testlower",
            "agent/y_test.go::TestInner",  # indented
        )
        for ev in bad:
            with self.subTest(ev=ev):
                p = self.check(doc(row(cls="TEST", evidence=f"`{ev}`")))
                self.assertEqual(len(p), 1, p)

    def test_test_file_must_exist(self):
        p = self.check(doc(row(cls="TEST", evidence="`tests/test_missing.py::test_x`")))
        self.assertEqual(len(p), 1, p)
        self.assertIn("does not exist", p[0])

    def test_threat_row_outside_recognised_table_is_error(self):
        other = "| Threat ID | Category | Threat | Class | Evidence | Notes |\n|---|---|---|---|---|---|\n"
        p = self.check("# t\n\n" + other + row("T-UPL-01"))
        self.assertEqual(len(p), 1, p)
        self.assertIn("outside a recognised threat table", p[0])
        # A non-pipe line ends the table early; later rows are no longer checked as rows.
        p = self.check(doc(row("T-UPL-01"), "stray prose\n", row("T-UPL-02")))
        self.assertEqual(len(p), 1, p)
        self.assertIn("T-UPL-02", p[0])
        self.assertIn("outside a recognised threat table", p[0])

    def test_real_verification_needs_a_value(self):
        for notes in ("real-verification:", "real-verification:   "):
            with self.subTest(notes=notes):
                p = self.check(doc(row("T-AUTH-01", cls="TEST", evidence=TEST_EV, notes=notes)))
                self.assertEqual(len(p), 1, p)
                self.assertIn("real-verification", p[0])

    def test_control_evidence_must_not_be_prose(self):
        for path in ("README.md", "notes.txt", "docs/x.rst"):
            with self.subTest(path=path):
                p = self.check(doc(row(evidence=f"`{path}::Guard` (L1)")))
                self.assertEqual(len(p), 1, p)
                self.assertIn("documentation", p[0])
        itself = self.root / "src/app.py"
        p = ctm.check(doc(row()), self.root, TODAY, doc_path=itself)
        self.assertEqual(len(p), 1, p)
        self.assertIn("the document itself", p[0])
        self.assertEqual(ctm.check(doc(row()), self.root, TODAY, doc_path=self.root / "x.md"), [])

    def test_accepted_keys_exactly_once_with_values(self):
        cases = {
            "duplicate reason": "reason: a; reason: b; owner: A; review: 2027-04-22",
            "duplicate owner": "reason: a; owner: A; owner: B; review: 2027-04-22",
            "duplicate review": "reason: a; owner: A; review: 2027-04-22; review: 2027-04-23",
            "empty reason": "reason:; owner: A; review: 2027-04-22",
            "empty owner": "reason: a; owner: ; review: 2027-04-22",
            "empty review": "reason: a; owner: A; review:",
            "key only inside value": "reason: a; owner: A; note: review: 2027-04-22",
        }
        for name, ev in cases.items():
            with self.subTest(name):
                p = self.accepted(ev)
                self.assertEqual(len(p), 1, p)
        self.assertEqual(self.accepted("reason: a: b; owner: A; review: 2027-04-22"), [])

    @unittest.skipUnless(REAL.exists(), "docs/security/threat_model.md not written yet")
    def test_real_threat_model(self):
        today = datetime.now(timezone.utc).date()
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(ctm.check(REAL.read_text(encoding="utf-8"), root, today, REAL), [])


if __name__ == "__main__":
    unittest.main()
