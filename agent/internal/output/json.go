// Package output defines the wire contract the scanner emits and uploads.
//
// These types are the Go mirror of backend/app/schemas/agent_scan.py
// (AgentScanPayload, FROZEN at schema_version "1.0"). The backend models use
// Pydantic extra="forbid", so this struct MUST NOT serialize any field the
// backend does not know about — every field below maps 1:1 onto the contract.
// Optional fields use `omitempty` so a missing value is dropped rather than sent
// as null/empty where the backend allows absence.
//
// The shared golden fixture (backend/tests/fixtures/agent_scan_v1.json, mirrored
// in agent/examples/inventory.sample.json) is the cross-language check: the JSON
// this package produces must validate against it. Bump SchemaVersion here and on
// the backend together if the shape ever changes.
package output

import (
	"encoding/json"
	"io"
)

// SchemaVersion is the frozen wire schema version. Must be in the backend's
// SUPPORTED_SCHEMA_VERSIONS set.
const SchemaVersion = "1.0"

// ScannerVersion is this binary's build version (semver). The backend enforces a
// MIN_AGENT_VERSION and rejects anything older with HTTP 426.
//
// It is a var (not a const) so the release pipeline can stamp the git tag at
// build time with -ldflags "-X .../internal/output.ScannerVersion=<semver>".
// The default below is the source-of-truth for local/dev builds and must stay a
// clean semver that the golden fixture expects.
var ScannerVersion = "0.1.0"

// Host describes the machine the scan ran on. Identity on the backend is the
// (org, agent token) pair, never the hostname — hostname here is descriptive.
type Host struct {
	Hostname  string `json:"hostname"`
	OSName    string `json:"os_name,omitempty"`
	OSVersion string `json:"os_version,omitempty"`
	Arch      string `json:"arch,omitempty"`
	IPAddress string `json:"ip_address,omitempty"`
}

// Software is one installed package. Vendor and product are required by the
// contract; for package managers that do not expose a vendor we set vendor =
// product (documented in the README).
type Software struct {
	Vendor  string `json:"vendor"`
	Product string `json:"product"`
	Version string `json:"version,omitempty"`
}

// Service is a running service unit (e.g. from systemctl).
type Service struct {
	Name  string `json:"name"`
	State string `json:"state,omitempty"`
}

// Port is a listening port, collected only with --include-ports.
type Port struct {
	Port     int    `json:"port"`
	Protocol string `json:"protocol"`
	Process  string `json:"process,omitempty"`
}

// Scan is the full upload body POSTed to /api/v1/inventory/scans.
type Scan struct {
	SchemaVersion  string     `json:"schema_version"`
	ScanID         string     `json:"scan_id"`
	Nonce          string     `json:"nonce"`
	ScannerVersion string     `json:"scanner_version"`
	Host           Host       `json:"host"`
	Software       []Software `json:"software"`
	Services       []Service  `json:"services"`
	Ports          []Port     `json:"ports"`
}

// New builds a Scan with the frozen schema/scanner versions and the supplied
// per-attempt scanID/nonce. Slices are normalized to empty (never nil) so they
// always serialize as [] — the backend defaults them to [] and forbids null.
func New(scanID, nonce string, host Host, software []Software, services []Service, ports []Port) Scan {
	if software == nil {
		software = []Software{}
	}
	if services == nil {
		services = []Service{}
	}
	if ports == nil {
		ports = []Port{}
	}
	return Scan{
		SchemaVersion:  SchemaVersion,
		ScannerVersion: ScannerVersion,
		ScanID:         scanID,
		Nonce:          nonce,
		Host:           host,
		Software:       software,
		Services:       services,
		Ports:          ports,
	}
}

// Marshal renders the scan as indented JSON (for --print / --output).
func (s Scan) Marshal() ([]byte, error) {
	return json.MarshalIndent(s, "", "  ")
}

// Write renders the scan as indented JSON to w with a trailing newline.
func (s Scan) Write(w io.Writer) error {
	b, err := s.Marshal()
	if err != nil {
		return err
	}
	if _, err := w.Write(b); err != nil {
		return err
	}
	_, err = w.Write([]byte("\n"))
	return err
}
