import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import check_sbom as cs

FIXTURE_PATH = Path(__file__).with_name("testdata") / "sbom_valid.cdx.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
VERSION = "v0.0.0-dev"
GO = "go1.27.3"


def fixture():
    return copy.deepcopy(FIXTURE)


class CheckSbomTests(unittest.TestCase):
    def test_fixture_is_what_we_expect(self):
        # Guards the fixture itself: if it is regenerated, update GO above.
        self.assertEqual(FIXTURE["metadata"]["component"]["version"], VERSION)
        self.assertEqual(
            [c["version"] for c in FIXTURE["components"] if c["name"] == "std"], [GO]
        )

    def test_valid_sbom_passes(self):
        self.assertEqual(cs.check(fixture(), VERSION, GO), [])

    def test_wrong_main_version_fails(self):
        problems = cs.check(fixture(), "v0.1.0", GO)
        self.assertTrue(any("main component version" in p for p in problems), problems)

    def test_devel_main_version_fails(self):
        sbom = fixture()
        sbom["metadata"]["component"]["version"] = "(devel)"
        self.assertNotEqual(cs.check(sbom, VERSION, GO), [])
        self.assertNotEqual(cs.check(sbom, "(devel)", GO), [])

    def test_missing_main_component_fails(self):
        sbom = fixture()
        del sbom["metadata"]["component"]
        self.assertNotEqual(cs.check(sbom, VERSION, GO), [])

    def test_missing_stdlib_fails(self):
        sbom = fixture()
        sbom["components"] = [c for c in sbom["components"] if c["name"] != "std"]
        problems = cs.check(sbom, VERSION, GO)
        self.assertTrue(any("stdlib" in p for p in problems), problems)

    def test_wrong_go_version_fails(self):
        problems = cs.check(fixture(), VERSION, "go1.20.0")
        self.assertTrue(any("stdlib" in p for p in problems), problems)

    def test_not_cyclonedx_fails(self):
        sbom = fixture()
        sbom["bomFormat"] = "SPDX"
        problems = cs.check(sbom, VERSION, GO)
        self.assertTrue(any("CycloneDX" in p for p in problems), problems)

    def test_non_object_fails(self):
        self.assertNotEqual(cs.check([], VERSION, GO), [])

    def test_cli_exit_codes(self):
        argv = [str(FIXTURE_PATH), "--version", VERSION, "--go-version", GO]
        self.assertEqual(cs.main(argv), 0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cs.main([str(FIXTURE_PATH), "--version", "v9.9.9", "--go-version", GO])
        self.assertEqual(rc, 1)
        self.assertTrue(buf.getvalue().startswith("::error::"))

    def test_cli_unreadable_file_exits_1(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cs.main(["no-such-file.json", "--version", VERSION, "--go-version", GO])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
