package collectors

import (
	"bufio"
	"os/exec"
	"strconv"
	"strings"

	"github.com/firegiant9000/hacker-tracker/agent/internal/output"
)

// CollectPorts lists listening TCP/UDP ports via `ss`. Only invoked when the
// operator passes --include-ports (off by default: listening sockets are more
// sensitive than a package list). Returns an empty slice when ss is missing.
func CollectPorts() []output.Port {
	if _, err := exec.LookPath("ss"); err != nil {
		return []output.Port{}
	}
	// -t tcp, -u udp, -l listening, -n numeric, -p process, -e extended.
	out, err := exec.Command("ss", "-tulpen").Output()
	if err != nil {
		return []output.Port{}
	}
	return parseSS(string(out))
}

// parseSS parses `ss -tulpen` output into Port rows. Layout (header first line):
//
//	Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process
//	tcp   LISTEN 0      128    0.0.0.0:22         0.0.0.0:*         users:(("sshd",pid=...))
//
// We extract the protocol (Netid), the local port, and a best-effort process
// name from the users:(("name",...)) field.
func parseSS(out string) []output.Port {
	ports := []output.Port{}
	seen := map[string]bool{} // dedupe (proto, port, process) across v4/v6 rows
	sc := bufio.NewScanner(strings.NewReader(out))
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 5 {
			continue
		}
		proto := strings.ToLower(fields[0])
		if proto != "tcp" && proto != "udp" {
			// Skip the header row ("Netid") and anything unexpected.
			continue
		}
		port, ok := localPort(fields[4])
		if !ok {
			continue
		}
		process := processName(line)
		key := proto + ":" + strconv.Itoa(port) + ":" + process
		if seen[key] {
			continue
		}
		seen[key] = true
		ports = append(ports, output.Port{Port: port, Protocol: proto, Process: process})
	}
	return ports
}

// localPort extracts the numeric port from a "Local Address:Port" token,
// handling IPv6 bracket-less forms like "[::]:443" and "0.0.0.0:22" by taking
// the substring after the final colon.
func localPort(addr string) (int, bool) {
	idx := strings.LastIndex(addr, ":")
	if idx < 0 || idx == len(addr)-1 {
		return 0, false
	}
	p, err := strconv.Atoi(addr[idx+1:])
	if err != nil || p < 0 || p > 65535 {
		return 0, false
	}
	return p, true
}

// processName pulls the first process name out of an ss users:(("name",...))
// field. Returns "" if no process info is present (e.g. ss run without root).
func processName(line string) string {
	const marker = `users:(("`
	i := strings.Index(line, marker)
	if i < 0 {
		return ""
	}
	rest := line[i+len(marker):]
	end := strings.Index(rest, `"`)
	if end < 0 {
		return ""
	}
	return rest[:end]
}
