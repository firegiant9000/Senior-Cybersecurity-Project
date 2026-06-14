package collectors

import "testing"

func TestParseSS(t *testing.T) {
	out := "" +
		"Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n" +
		`tcp   LISTEN 0      128    0.0.0.0:22         0.0.0.0:*         users:(("sshd",pid=900,fd=3))` + "\n" +
		`tcp   LISTEN 0      511    [::]:443           [::]:*           users:(("nginx",pid=1200,fd=6))` + "\n" +
		`udp   UNCONN 0      0      0.0.0.0:68         0.0.0.0:*         users:(("dhclient",pid=700,fd=5))` + "\n" +
		`tcp   LISTEN 0      128    0.0.0.0:22         0.0.0.0:*         users:(("sshd",pid=901,fd=4))` + "\n" // dup (proto,port,process)

	got := parseSS(out)
	if len(got) != 3 {
		t.Fatalf("expected 3 unique ports, got %d: %+v", len(got), got)
	}

	want := map[int]struct {
		proto   string
		process string
	}{
		22:  {"tcp", "sshd"},
		443: {"tcp", "nginx"},
		68:  {"udp", "dhclient"},
	}
	for _, p := range got {
		w, ok := want[p.Port]
		if !ok {
			t.Errorf("unexpected port %d", p.Port)
			continue
		}
		if p.Protocol != w.proto || p.Process != w.process {
			t.Errorf("port %d = %+v, want proto=%s process=%s", p.Port, p, w.proto, w.process)
		}
	}
}

func TestLocalPort(t *testing.T) {
	cases := map[string]int{
		"0.0.0.0:22": 22,
		"[::]:443":   443,
		"127.0.0.1":  -1, // no port
		"host:bad":   -1, // non-numeric
	}
	for addr, want := range cases {
		got, ok := localPort(addr)
		if want == -1 {
			if ok {
				t.Errorf("localPort(%q) should fail, got %d", addr, got)
			}
			continue
		}
		if !ok || got != want {
			t.Errorf("localPort(%q) = %d (%v), want %d", addr, got, ok, want)
		}
	}
}
