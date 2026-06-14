package output

import (
	"encoding/json"
	"reflect"
	"sort"
	"testing"
)

// goldenFixture mirrors backend/tests/fixtures/agent_scan_v1.json — the shared
// cross-language contract. If the backend bumps the fixture, update this and the
// SchemaVersion constant together.
const goldenFixture = `{
  "schema_version": "1.0",
  "scan_id": "11111111-1111-4111-8111-111111111111",
  "nonce": "a1b2c3d4e5f6",
  "scanner_version": "0.1.0",
  "host": {
    "hostname": "web-01.example.com",
    "os_name": "Ubuntu",
    "os_version": "22.04",
    "arch": "x86_64",
    "ip_address": "10.0.0.10"
  },
  "software": [
    { "vendor": "OpenSSL", "product": "OpenSSL", "version": "3.0.2" },
    { "vendor": "nginx", "product": "nginx", "version": "1.18.0" },
    { "vendor": "OpenBSD", "product": "OpenSSH", "version": "8.9p1" }
  ],
  "services": [
    { "name": "nginx.service", "state": "running" },
    { "name": "ssh.service", "state": "running" }
  ],
  "ports": [
    { "port": 443, "protocol": "tcp", "process": "nginx" },
    { "port": 22, "protocol": "tcp", "process": "sshd" }
  ]
}`

// TestGoldenFixtureRoundTrips proves the Go struct can decode the shared golden
// fixture and re-encode it to an equivalent value — i.e. no field is dropped or
// renamed relative to the frozen backend contract.
func TestGoldenFixtureRoundTrips(t *testing.T) {
	var fromFixture Scan
	if err := json.Unmarshal([]byte(goldenFixture), &fromFixture); err != nil {
		t.Fatalf("golden fixture failed to decode into Scan: %v", err)
	}

	if fromFixture.SchemaVersion != SchemaVersion {
		t.Errorf("schema_version = %q, scanner constant = %q", fromFixture.SchemaVersion, SchemaVersion)
	}
	if len(fromFixture.Software) != 3 || len(fromFixture.Services) != 2 || len(fromFixture.Ports) != 2 {
		t.Fatalf("unexpected counts: sw=%d svc=%d ports=%d",
			len(fromFixture.Software), len(fromFixture.Services), len(fromFixture.Ports))
	}

	reencoded, err := json.Marshal(fromFixture)
	if err != nil {
		t.Fatalf("re-encode failed: %v", err)
	}
	var back Scan
	if err := json.Unmarshal(reencoded, &back); err != nil {
		t.Fatalf("re-decode failed: %v", err)
	}
	if !reflect.DeepEqual(fromFixture, back) {
		t.Errorf("round trip changed the value:\n got  %+v\n want %+v", back, fromFixture)
	}
}

// TestNoExtraTopLevelKeys guards the backend's extra="forbid": the marshaled
// scan must contain exactly the contract's top-level keys and nothing more.
func TestNoExtraTopLevelKeys(t *testing.T) {
	scan := New(
		"11111111-1111-4111-8111-111111111111",
		"a1b2c3d4e5f6",
		Host{Hostname: "h"},
		nil, nil, nil,
	)
	b, err := json.Marshal(scan)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatal(err)
	}
	got := make([]string, 0, len(m))
	for k := range m {
		got = append(got, k)
	}
	sort.Strings(got)
	want := []string{"host", "nonce", "ports", "scan_id", "scanner_version", "schema_version", "services", "software"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("top-level keys = %v, want %v", got, want)
	}
}

// TestNewNormalizesNilSlices ensures empty collections serialize as [] (the
// backend forbids null for software/services/ports).
func TestNewNormalizesNilSlices(t *testing.T) {
	scan := New("id", "nonce", Host{Hostname: "h"}, nil, nil, nil)
	if scan.Software == nil || scan.Services == nil || scan.Ports == nil {
		t.Fatal("New must replace nil slices with empty slices")
	}
	b, _ := json.Marshal(scan)
	var m map[string]json.RawMessage
	_ = json.Unmarshal(b, &m)
	for _, k := range []string{"software", "services", "ports"} {
		if string(m[k]) != "[]" {
			t.Errorf("%s serialized as %s, want []", k, m[k])
		}
	}
}
