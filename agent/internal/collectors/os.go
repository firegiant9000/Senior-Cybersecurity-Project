// Package collectors gathers read-only host inventory on Linux.
//
// READ-ONLY GUARANTEE: every collector here only runs well-known read commands
// (dpkg-query, rpm, systemctl, ss) or reads /etc/os-release. The scanner never
// reads file contents, browser history, secrets, environment variables, or user
// documents. See agent/README.md for the full collected / does-not-collect list.
package collectors

import (
	"bufio"
	"net"
	"os"
	"os/exec"
	"strings"

	"github.com/firegiant9000/hacker-tracker/agent/internal/output"
)

// CollectHost gathers descriptive host metadata. Every field is best-effort: a
// missing value is left empty rather than failing the whole scan, because the
// backend treats os/arch/ip as optional.
func CollectHost() output.Host {
	h := output.Host{}
	if name, err := os.Hostname(); err == nil {
		h.Hostname = name
	}
	h.Arch = collectArch()
	osName, osVersion := parseOSRelease(readOSRelease())
	h.OSName = osName
	h.OSVersion = osVersion
	h.IPAddress = primaryIP()
	return h
}

// collectArch returns the machine hardware name (e.g. "x86_64", "aarch64") from
// `uname -m`, matching the values real Linux tooling reports.
func collectArch() string {
	out, err := exec.Command("uname", "-m").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func readOSRelease() string {
	// /etc/os-release is the freedesktop standard; /usr/lib/os-release is the
	// vendor fallback when /etc is empty.
	for _, p := range []string{"/etc/os-release", "/usr/lib/os-release"} {
		if b, err := os.ReadFile(p); err == nil {
			return string(b)
		}
	}
	return ""
}

// parseOSRelease extracts NAME and VERSION_ID from os-release contents. Exposed
// (lowercase but package-internal) and pure so it is unit-testable without a
// filesystem.
func parseOSRelease(contents string) (name, version string) {
	sc := bufio.NewScanner(strings.NewReader(contents))
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		key, val, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		val = strings.Trim(strings.TrimSpace(val), `"'`)
		switch key {
		case "NAME":
			name = val
		case "VERSION_ID":
			version = val
		}
	}
	return name, version
}

// primaryIP returns the host's primary outbound IPv4 by inspecting the route to
// a public address. No packets are sent (UDP "dial" only resolves the local
// source address); returns "" if it cannot be determined.
func primaryIP() string {
	conn, err := net.Dial("udp", "8.8.8.8:80")
	if err != nil {
		return ""
	}
	defer conn.Close()
	if addr, ok := conn.LocalAddr().(*net.UDPAddr); ok {
		return addr.IP.String()
	}
	return ""
}
