// Package upload posts a collected scan to the Hacker Tracker backend using the
// agent bearer token, and polls the resulting scan_run for status.
//
// It speaks exactly the Phase 3 contract: POST /api/v1/inventory/scans with
// Authorization: Bearer ht_<prefix>_<secret>, and GET .../{id} to poll. The
// distinct HTTP statuses the backend returns (401/409/422/426) are translated
// into actionable errors so the operator sees "upgrade the scanner" rather than
// a raw 426.
package upload

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/firegiant9000/hacker-tracker/agent/internal/output"
)

const (
	scansPath = "/api/v1/inventory/scans"
)

// Accepted mirrors the backend ScanUploadAccepted response (201).
type Accepted struct {
	ScanRunID     int    `json:"scan_run_id"`
	Status        string `json:"status"`
	AssetCount    int    `json:"asset_count"`
	SoftwareCount int    `json:"software_count"`
}

// ErrUpgradeRequired is returned on HTTP 426 — the backend's MIN_AGENT_VERSION
// is newer than this build. main() reports it as a graceful "please upgrade".
var ErrUpgradeRequired = errors.New("scanner version is below the server minimum; please upgrade")

// Client uploads scans to a backend base URL ("https://api.example.com", no
// trailing path) using a bearer token.
type Client struct {
	BaseURL string
	Token   string
	HTTP    *http.Client
}

// New builds a Client with a sane default timeout. baseURL is trimmed of a
// trailing slash so joining the API path never double-slashes.
func New(baseURL, token string, timeout time.Duration) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		Token:   token,
		HTTP:    &http.Client{Timeout: timeout},
	}
}

// Upload POSTs the scan and returns the accepted scan_run summary. The bearer
// token is sent verbatim (the backend expects the raw ht_<prefix>_<secret>).
func (c *Client) Upload(ctx context.Context, scan output.Scan) (*Accepted, error) {
	body, err := json.Marshal(scan)
	if err != nil {
		return nil, fmt.Errorf("marshal scan: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+scansPath, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "hacker-tracker-agent/"+output.ScannerVersion)

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, fmt.Errorf("upload request failed: %w", err)
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 64*1024))

	switch resp.StatusCode {
	case http.StatusCreated:
		var acc Accepted
		if err := json.Unmarshal(respBody, &acc); err != nil {
			return nil, fmt.Errorf("decode accepted response: %w", err)
		}
		return &acc, nil
	case http.StatusUnauthorized:
		return nil, fmt.Errorf("token rejected (401): %s", detail(respBody))
	case http.StatusConflict:
		return nil, fmt.Errorf("scan rejected as a duplicate/replay (409): %s", detail(respBody))
	case http.StatusUpgradeRequired:
		return nil, ErrUpgradeRequired
	case http.StatusUnprocessableEntity:
		return nil, fmt.Errorf("payload rejected (422): %s", detail(respBody))
	default:
		return nil, fmt.Errorf("upload failed (HTTP %d): %s", resp.StatusCode, detail(respBody))
	}
}

// PollStatus fetches the current scan_run status once (GET .../{id}). The agent
// can call this in a loop to watch the matcher complete; main() does a couple of
// polite polls and then prints a "check the dashboard" hint.
func (c *Client) PollStatus(ctx context.Context, scanRunID int) (string, error) {
	url := fmt.Sprintf("%s%s/%d", c.BaseURL, scansPath, scanRunID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Accept", "application/json")

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(io.LimitReader(resp.Body, 64*1024))
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("poll failed (HTTP %d): %s", resp.StatusCode, detail(respBody))
	}
	var run struct {
		Status string `json:"status"`
	}
	if err := json.Unmarshal(respBody, &run); err != nil {
		return "", fmt.Errorf("decode scan_run: %w", err)
	}
	return run.Status, nil
}

// detail best-effort extracts FastAPI's {"detail": "..."} message; falls back to
// the raw (truncated) body so the operator always sees something useful.
func detail(body []byte) string {
	var parsed struct {
		Detail json.RawMessage `json:"detail"`
	}
	if err := json.Unmarshal(body, &parsed); err == nil && len(parsed.Detail) > 0 {
		var s string
		if json.Unmarshal(parsed.Detail, &s) == nil {
			return s
		}
		return string(parsed.Detail)
	}
	s := strings.TrimSpace(string(body))
	if len(s) > 300 {
		s = s[:300] + "…"
	}
	if s == "" {
		return "(no response body)"
	}
	return s
}
