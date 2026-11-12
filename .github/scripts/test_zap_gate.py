import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import zap_gate

HEADER = (
    "# Scan exceptions\n\n## Exceptions\n\n"
    "| ID | Scanner | Package / location | Reason | Compensating control | Added | Expires |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
)


def alert(pluginid, riskcode, name="Test alert", instances=1):
    return {
        "pluginid": pluginid,
        "riskcode": riskcode,
        "riskdesc": "Medium (High)",
        "name": name,
        "instances": [{}] * instances,
    }


def report(*sites):
    return {"site": [{"alerts": list(alerts)} for alerts in sites]}


class FailingAlertsTest(unittest.TestCase):
    def test_medium_alert_fails(self):
        result = zap_gate.failing_alerts(report([alert("10038", "2")]), set())
        self.assertEqual([a["pluginid"] for a in result], ["10038"])

    def test_high_alert_fails(self):
        result = zap_gate.failing_alerts(report([alert("40012", "3")]), set())
        self.assertEqual(len(result), 1)

    def test_low_and_info_pass(self):
        result = zap_gate.failing_alerts(report([alert("1", "1"), alert("2", "0")]), set())
        self.assertEqual(result, [])

    def test_ignored_plugin_passes(self):
        result = zap_gate.failing_alerts(report([alert("10038", "2")]), {"10038"})
        self.assertEqual(result, [])

    def test_multiple_sites_are_all_checked(self):
        result = zap_gate.failing_alerts(report([alert("1", "0")], [alert("10038", "2")]), set())
        self.assertEqual([a["pluginid"] for a in result], ["10038"])

    def test_single_site_dict_is_accepted(self):
        rep = {"site": {"alerts": [alert("10038", "2")]}}
        self.assertEqual(len(zap_gate.failing_alerts(rep, set())), 1)

    def test_missing_site_or_alerts_passes(self):
        self.assertEqual(zap_gate.failing_alerts({}, set()), [])
        self.assertEqual(zap_gate.failing_alerts({"site": [{}]}, set()), [])


class CliTest(unittest.TestCase):
    def _run(self, rep, exceptions_md):
        with tempfile.TemporaryDirectory() as d:
            rp = Path(d) / "zap.json"
            rp.write_text(json.dumps(rep), encoding="utf-8")
            ep = Path(d) / "scan_exceptions.md"
            ep.write_text(exceptions_md, encoding="utf-8")
            return zap_gate.main([str(rp), str(ep)])

    @staticmethod
    def _row(added, expires):
        return f"| 10038 | zap | site | reason | control | {added} | {expires} |\n"

    def test_active_exception_passes(self):
        today = datetime.now(timezone.utc).date()
        md = HEADER + self._row(today, today + timedelta(days=30))
        self.assertEqual(self._run(report([alert("10038", "2")]), md), 0)

    def test_expired_exception_not_ignored(self):
        today = datetime.now(timezone.utc).date()
        md = HEADER + self._row(today - timedelta(days=30), today - timedelta(days=1))
        self.assertEqual(self._run(report([alert("10038", "2")]), md), 1)

    def test_output_line_format(self):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self._run(report([alert("10038", "2", "CSP Header Not Set", 3)]), HEADER)
        self.assertEqual(code, 1)
        self.assertEqual(buf.getvalue().strip(), "10038 Medium (High) CSP Header Not Set (3 instances)")

    def test_unreadable_report_fails(self):
        self.assertEqual(zap_gate.main(["does-not-exist.json", "does-not-exist.md"]), 1)


if __name__ == "__main__":
    unittest.main()
