package collectors

import (
	"bufio"
	"os/exec"
	"strings"

	"github.com/firegiant9000/hacker-tracker/agent/internal/output"
)

// SoftwareResult is the outcome of package collection: the rows plus which
// package manager produced them (for the README's "no silent gaps" promise —
// main() surfaces this so an unsupported distro is reported, not hidden).
type SoftwareResult struct {
	PackageManager string // "dpkg", "rpm", or "" if none detected
	Software       []output.Software
}

// CollectSoftware detects the host's package manager and lists installed
// packages. dpkg (Debian/Ubuntu) is preferred when both are present. Returns an
// empty result with PackageManager="" on an unsupported distro — the caller is
// expected to warn rather than silently report zero software.
func CollectSoftware() (SoftwareResult, error) {
	if _, err := exec.LookPath("dpkg-query"); err == nil {
		out, err := dpkgQuery()
		if err != nil {
			return SoftwareResult{PackageManager: "dpkg"}, err
		}
		return SoftwareResult{PackageManager: "dpkg", Software: parseDpkg(out)}, nil
	}
	if _, err := exec.LookPath("rpm"); err == nil {
		out, err := rpmQuery()
		if err != nil {
			return SoftwareResult{PackageManager: "rpm"}, err
		}
		return SoftwareResult{PackageManager: "rpm", Software: parseRPM(out)}, nil
	}
	return SoftwareResult{}, nil
}

func dpkgQuery() (string, error) {
	// Status is included so we can drop half-installed/config-only packages.
	out, err := exec.Command(
		"dpkg-query", "-W", "-f=${Package}\t${Version}\t${db:Status-Abbrev}\n",
	).Output()
	return string(out), err
}

func rpmQuery() (string, error) {
	out, err := exec.Command(
		"rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\t%{VENDOR}\n",
	).Output()
	return string(out), err
}

// parseDpkg turns `dpkg-query -W` output into Software rows. dpkg has no vendor
// concept, so vendor = product = package name. Only fully-installed packages
// (status abbrev "ii") are kept.
func parseDpkg(out string) []output.Software {
	sw := []output.Software{}
	sc := bufio.NewScanner(strings.NewReader(out))
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for sc.Scan() {
		fields := strings.Split(sc.Text(), "\t")
		if len(fields) < 2 {
			continue
		}
		name := strings.TrimSpace(fields[0])
		version := strings.TrimSpace(fields[1])
		if len(fields) >= 3 {
			status := strings.TrimSpace(fields[2])
			// Status-Abbrev is e.g. "ii " (installed). Anything not desired+
			// installed ("ii") is config-only/removed/half-installed — skip it.
			if !strings.HasPrefix(status, "ii") {
				continue
			}
		}
		if name == "" {
			continue
		}
		sw = append(sw, output.Software{Vendor: name, Product: name, Version: version})
	}
	return sw
}

// parseRPM turns `rpm -qa` output into Software rows. rpm exposes a vendor,
// which we use when present and meaningful; otherwise we fall back to the
// package name so the required vendor field is never empty.
func parseRPM(out string) []output.Software {
	sw := []output.Software{}
	sc := bufio.NewScanner(strings.NewReader(out))
	sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for sc.Scan() {
		fields := strings.Split(sc.Text(), "\t")
		if len(fields) < 2 {
			continue
		}
		name := strings.TrimSpace(fields[0])
		version := strings.TrimSpace(fields[1])
		if name == "" {
			continue
		}
		vendor := name
		if len(fields) >= 3 {
			v := strings.TrimSpace(fields[2])
			// rpm prints "(none)" when a package declares no vendor.
			if v != "" && v != "(none)" {
				vendor = v
			}
		}
		sw = append(sw, output.Software{Vendor: vendor, Product: name, Version: version})
	}
	return sw
}

// CollectServices lists running systemd service units. Returns an empty slice
// (no error) when systemctl is unavailable — services are descriptive metadata,
// not a hard requirement.
func CollectServices() []output.Service {
	if _, err := exec.LookPath("systemctl"); err != nil {
		return []output.Service{}
	}
	out, err := exec.Command(
		"systemctl", "list-units", "--type=service", "--state=running",
		"--no-legend", "--no-pager", "--plain",
	).Output()
	if err != nil {
		return []output.Service{}
	}
	return parseSystemctl(string(out))
}

// parseSystemctl parses `systemctl list-units` plain output. Columns are
// whitespace-separated: UNIT LOAD ACTIVE SUB DESCRIPTION. We keep UNIT (name)
// and SUB (the fine-grained state, e.g. "running").
func parseSystemctl(out string) []output.Service {
	svcs := []output.Service{}
	sc := bufio.NewScanner(strings.NewReader(out))
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}
		svcs = append(svcs, output.Service{Name: fields[0], State: fields[3]})
	}
	return svcs
}
