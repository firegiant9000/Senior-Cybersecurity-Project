import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import scan_exceptions as se

SCRIPT = Path(__file__).with_name("scan_exceptions.py")

HEADER = (
    "# Scan exceptions\n\nPolicy text.\n\n## Exceptions\n\n"
    "| ID | Scanner | Package / location | Reason | Compensating control | Added | Expires |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
)


def row(id_="EX-1", scanner="trivy", added="2026-10-20", expires="2026-12-01"):
    return f"| {id_} | {scanner} | pkg | reason | control | {added} | {expires} |\n"


def entry(id_, scanner, added, expires):
    return se.ScanException(id_, scanner, "pkg", "reason", "control", added, expires)


class ParseTests(unittest.TestCase):
    def test_empty_table_is_valid(self):
        self.assertEqual(se.parse_exceptions(HEADER), [])
        self.assertEqual(se.validate([], date(2026, 10, 20)), [])

    def test_parses_row(self):
        entries = se.parse_exceptions(HEADER + row())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].id, "EX-1")
        self.assertEqual(entries[0].expires, date(2026, 12, 1))

    def test_bad_date_raises(self):
        with self.assertRaisesRegex(ValueError, "EX-1"):
            se.parse_exceptions(HEADER + row(expires="2026-13-45"))

    def test_unknown_scanner_raises(self):
        with self.assertRaisesRegex(ValueError, "EX-1"):
            se.parse_exceptions(HEADER + row(scanner="nope"))

    def test_wrong_cell_count_raises(self):
        with self.assertRaises(ValueError):
            se.parse_exceptions(HEADER + "| EX-1 | trivy | pkg |\n")


class ValidateTests(unittest.TestCase):
    def test_expires_today_is_valid(self):
        e = entry("EX-1", "trivy", date(2026, 10, 1), date(2026, 10, 20))
        self.assertEqual(se.validate([e], date(2026, 10, 20)), [])

    def test_expired_yesterday_fails(self):
        e = entry("EX-1", "trivy", date(2026, 10, 1), date(2026, 10, 19))
        errors = se.validate([e], date(2026, 10, 20))
        self.assertEqual(len(errors), 1)
        self.assertIn("EX-1", errors[0])

    def test_window_over_90_days_fails(self):
        added = date(2026, 10, 20)
        over = entry("EX-1", "trivy", added, date(2027, 1, 19))
        ok = entry("EX-2", "trivy", added, date(2027, 1, 18))
        self.assertEqual(len(se.validate([over], added)), 1)
        self.assertIn("EX-1", se.validate([over], added)[0])
        self.assertEqual(se.validate([ok], added), [])

    def test_expires_before_added_fails(self):
        e = entry("EX-1", "trivy", date(2026, 10, 20), date(2026, 10, 10))
        errors = se.validate([e], date(2026, 10, 1))
        self.assertEqual(len(errors), 1)
        self.assertIn("EX-1", errors[0])


class ActiveIdsTests(unittest.TestCase):
    def test_active_ids_filters_scanner_and_expiry(self):
        today = date(2026, 10, 20)
        entries = [
            entry("T-OLD", "trivy", date(2026, 8, 1), date(2026, 10, 19)),
            entry("T-NEW", "trivy", date(2026, 10, 1), date(2026, 11, 1)),
            entry("P-1", "pip-audit", date(2026, 10, 1), date(2026, 11, 1)),
        ]
        self.assertEqual(se.active_ids(entries, "trivy", today), ["T-NEW"])


class CliTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
        )

    def _file(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "ex.md"
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_cli_check_exit_codes(self):
        today = datetime.now(timezone.utc).date()
        valid = self._file(
            HEADER + row(added=str(today), expires=str(today + timedelta(days=30)))
        )
        expired = self._file(
            HEADER
            + row(
                added=str(today - timedelta(days=30)),
                expires=str(today - timedelta(days=1)),
            )
        )
        self.assertEqual(self._run("check", "--file", valid).returncode, 0)
        r = self._run("check", "--file", expired)
        self.assertEqual(r.returncode, 1)
        self.assertIn("EX-1", r.stdout + r.stderr)

    def test_cli_ids(self):
        today = datetime.now(timezone.utc).date()
        f = self._file(
            HEADER
            + row("A", "trivy", str(today), str(today + timedelta(days=5)))
            + row("B", "pip-audit", str(today), str(today + timedelta(days=5)))
        )
        r = self._run("ids", "trivy", "--file", f)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.split(), ["A"])


if __name__ == "__main__":
    unittest.main()
