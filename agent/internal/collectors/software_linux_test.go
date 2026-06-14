package collectors

import "testing"

func TestParseDpkg(t *testing.T) {
	out := "" +
		"nginx\t1.18.0-0ubuntu1\tii \n" +
		"openssl\t3.0.2-0ubuntu1.10\tii \n" +
		"removed-pkg\t1.0\trc \n" + // config-only: must be dropped
		"half\t2.0\tiU \n" + // not fully installed: dropped
		"\t9.9\tii \n" // empty name: dropped

	got := parseDpkg(out)
	if len(got) != 2 {
		t.Fatalf("expected 2 installed packages, got %d: %+v", len(got), got)
	}
	if got[0].Product != "nginx" || got[0].Vendor != "nginx" || got[0].Version != "1.18.0-0ubuntu1" {
		t.Errorf("unexpected first row: %+v", got[0])
	}
	if got[1].Product != "openssl" {
		t.Errorf("unexpected second row: %+v", got[1])
	}
}

func TestParseRPM(t *testing.T) {
	out := "" +
		"openssl\t3.0.7-1.el9\tRed Hat, Inc.\n" +
		"vim\t9.0-1\t(none)\n" + // vendor "(none)" → fall back to name
		"curl\t7.76.1-1\t\n" // empty vendor → fall back to name

	got := parseRPM(out)
	if len(got) != 3 {
		t.Fatalf("expected 3 packages, got %d", len(got))
	}
	if got[0].Vendor != "Red Hat, Inc." || got[0].Product != "openssl" {
		t.Errorf("vendor should be used when present: %+v", got[0])
	}
	if got[1].Vendor != "vim" {
		t.Errorf("(none) vendor should fall back to name: %+v", got[1])
	}
	if got[2].Vendor != "curl" {
		t.Errorf("empty vendor should fall back to name: %+v", got[2])
	}
}

func TestParseSystemctl(t *testing.T) {
	out := "" +
		"nginx.service   loaded active running A high performance web server\n" +
		"ssh.service     loaded active running OpenBSD Secure Shell server\n" +
		"\n" +
		"short.line\n" // too few columns: dropped

	got := parseSystemctl(out)
	if len(got) != 2 {
		t.Fatalf("expected 2 services, got %d: %+v", len(got), got)
	}
	if got[0].Name != "nginx.service" || got[0].State != "running" {
		t.Errorf("unexpected service: %+v", got[0])
	}
}

func TestParseOSRelease(t *testing.T) {
	contents := `NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
VERSION_ID="22.04"
ID=ubuntu`
	name, version := parseOSRelease(contents)
	if name != "Ubuntu" {
		t.Errorf("name = %q, want Ubuntu", name)
	}
	if version != "22.04" {
		t.Errorf("version = %q, want 22.04", version)
	}
}
