#!/usr/bin/env python3
"""Check that a CycloneDX SBOM describes the shipped agent binary.

Usage: check_sbom.py <sbom.json> --version vX.Y.Z --go-version goX.Y.Z

Exits 0 when valid; exits 1 and prints one ::error:: line per problem otherwise.

Field locations (cyclonedx-gomod v1.12.0, `bin -json -std -version vX.Y.Z`):
  bomFormat                          must be "CycloneDX"
  metadata.component.version         main module version (the -version flag);
                                     "(devel)" when the override did not take
  components[] with name == "std"    Go standard library, version == go env GOVERSION
"""
import argparse
import json
import sys


def check(sbom, version, go_version):
    """Return a list of problem strings; empty when the SBOM is valid."""
    if not isinstance(sbom, dict):
        return ["SBOM is not a JSON object"]
    problems = []

    if sbom.get("bomFormat") != "CycloneDX":
        problems.append(
            f"not a CycloneDX SBOM (bomFormat is {sbom.get('bomFormat')!r})"
        )

    metadata = sbom.get("metadata")
    main = metadata.get("component") if isinstance(metadata, dict) else None
    if not isinstance(main, dict):
        problems.append("SBOM has no main component (metadata.component)")
    else:
        got = main.get("version")
        if got == "(devel)":
            problems.append(
                f"main component version is '(devel)', expected {version!r}"
            )
        elif got != version:
            problems.append(f"main component version is {got!r}, expected {version!r}")

    components = sbom.get("components")
    if not isinstance(components, list):
        components = []
    std = [c for c in components if isinstance(c, dict) and c.get("name") == "std"]
    if not std:
        problems.append("stdlib component ('std') is missing")
    elif not any(c.get("version") == go_version for c in std):
        found = ", ".join(repr(c.get("version")) for c in std)
        problems.append(
            f"stdlib component version is {found}, expected {go_version!r}"
        )

    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sbom")
    parser.add_argument("--version", required=True)
    parser.add_argument("--go-version", required=True)
    args = parser.parse_args(argv)

    try:
        with open(args.sbom, encoding="utf-8") as fh:
            sbom = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"::error::cannot read SBOM {args.sbom}: {exc}")
        return 1

    problems = check(sbom, args.version, args.go_version)
    for p in problems:
        print(f"::error::{args.sbom}: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
