package upload

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/firegiant9000/hacker-tracker/agent/internal/output"
)

func TestNewRejectsPlainHTTPServer(t *testing.T) {
	cases := []string{
		"http://api.example.com",
		"http://hacker-tracker-backend.onrender.com",
		"http://localhost.example.com",
		"http://127.0.0.1.nip.io",
		"http://10.0.0.5:8000",
		"ftp://api.example.com",
		"api.example.com",
		"https://",
		"",
		"https://user:pw@api.example.com",
		"https://api.example.com?token=x",
		"https://api.example.com#x",
	}
	for _, raw := range cases {
		t.Run(raw, func(t *testing.T) {
			c, err := New(raw, "ht_abc_def", time.Second)
			if !errors.Is(err, ErrInsecureServer) {
				t.Fatalf("New(%q) error = %v, want ErrInsecureServer", raw, err)
			}
			if c != nil {
				t.Fatalf("New(%q) returned a non-nil client", raw)
			}
		})
	}
}

func TestNewAllowsHTTPSAndLoopbackHTTP(t *testing.T) {
	cases := []string{
		"https://api.example.com",
		"https://api.example.com/",
		"http://localhost:8000",
		"http://LOCALHOST:8000",
		"http://127.0.0.1:8000",
		"http://[::1]:8000",
	}
	for _, raw := range cases {
		t.Run(raw, func(t *testing.T) {
			c, err := New(raw, "ht_abc_def", time.Second)
			if err != nil {
				t.Fatalf("New(%q) error = %v, want nil", raw, err)
			}
			if got := c.BaseURL; len(got) > 0 && got[len(got)-1] == '/' {
				t.Fatalf("BaseURL %q keeps its trailing slash", got)
			}
		})
	}
}

func TestNewLowerCasesTheHost(t *testing.T) {
	cases := map[string]string{
		"http://LOCALHOST:8000":      "http://localhost:8000",
		"http://LocalHost:8000/":     "http://localhost:8000",
		"https://API.Example.com":    "https://api.example.com",
		"http://[::1]:8000":          "http://[::1]:8000",
		"https://api.example.com/x/": "https://api.example.com/x",
	}
	for raw, want := range cases {
		c, err := New(raw, "ht_abc_def", time.Second)
		if err != nil {
			t.Fatalf("New(%q): %v", raw, err)
		}
		if c.BaseURL != want {
			t.Fatalf("New(%q).BaseURL = %q, want %q", raw, c.BaseURL, want)
		}
	}
}

func TestPlainHTTPNeverUsesAProxy(t *testing.T) {
	t.Setenv("HTTP_PROXY", "http://proxy.invalid:3128")
	t.Setenv("http_proxy", "http://proxy.invalid:3128")
	c, err := New("http://localhost:8000", "ht_abc_def", time.Second)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	proxy := c.HTTP.Transport.(*http.Transport).Proxy
	req, _ := http.NewRequest(http.MethodPost, "http://localhost:8000/x", nil)
	got, err := proxy(req)
	if err != nil || got != nil {
		t.Fatalf("Proxy(http://localhost:8000/x) = %v, %v; want nil, nil", got, err)
	}
}

func TestInsecureErrorOmitsCredentialsAndQuery(t *testing.T) {
	err := ValidateServerURL("http://user:secret@api.example.com/p?token=ht_abc_def")
	if !errors.Is(err, ErrInsecureServer) {
		t.Fatalf("error = %v, want ErrInsecureServer", err)
	}
	for _, leak := range []string{"secret", "user", "token", "ht_abc_def"} {
		if strings.Contains(err.Error(), leak) {
			t.Fatalf("error %q leaks %q", err.Error(), leak)
		}
	}
}

func TestClientDoesNotFollowRedirects(t *testing.T) {
	var hits atomic.Int32
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits.Add(1)
		w.WriteHeader(http.StatusCreated)
	}))
	defer target.Close()
	origin := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, target.URL+r.URL.Path, http.StatusTemporaryRedirect)
	}))
	defer origin.Close()

	c, err := New(origin.URL, "ht_abc_def", 5*time.Second)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, err = c.Upload(context.Background(), output.New("id", "nonce", output.Host{Hostname: "h"}, nil, nil, nil))
	if !errors.Is(err, ErrRedirectRefused) {
		t.Fatalf("error = %v, want ErrRedirectRefused", err)
	}
	if n := hits.Load(); n != 0 {
		t.Fatalf("redirect target was hit %d times, want 0", n)
	}
}

func TestRetryAfterParsing(t *testing.T) {
	cases := map[string]time.Duration{
		"":                              5 * time.Second,
		"5":                             5 * time.Second,
		"0":                             0,
		"12":                            12 * time.Second,
		"-3":                            5 * time.Second,
		"9999":                          30 * time.Second,
		"Wed, 21 Oct 2026 07:28:00 GMT": 5 * time.Second,
		"soon":                          5 * time.Second,
	}
	for in, want := range cases {
		h := http.Header{}
		if in != "" {
			h.Set("Retry-After", in)
		}
		if got := retryAfter(h); got != want {
			t.Errorf("retryAfter(%q) = %v, want %v", in, got, want)
		}
	}
}

func retryTestScan() output.Scan {
	return output.New("id", "nonce", output.Host{Hostname: "h"}, nil, nil, nil)
}

func newRetryClient(t *testing.T, url string) (*Client, *[]time.Duration) {
	t.Helper()
	c, err := New(url, "ht_abc_def", 5*time.Second)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	waits := &[]time.Duration{}
	c.sleep = func(_ context.Context, d time.Duration) error {
		*waits = append(*waits, d)
		return nil
	}
	return c, waits
}

func TestUploadRetriesOn503ThenSucceeds(t *testing.T) {
	var bodies [][]byte
	var auths []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		bodies = append(bodies, b)
		auths = append(auths, r.Header.Get("Authorization"))
		if len(bodies) <= 2 {
			w.Header().Set("Retry-After", "7")
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"scan_run_id":1,"status":"queued","asset_count":1,"software_count":2}`))
	}))
	defer srv.Close()

	c, waits := newRetryClient(t, srv.URL)
	acc, err := c.Upload(context.Background(), retryTestScan())
	if err != nil {
		t.Fatalf("Upload: %v", err)
	}
	if acc.ScanRunID != 1 {
		t.Errorf("ScanRunID = %d, want 1", acc.ScanRunID)
	}
	if len(bodies) != 3 {
		t.Fatalf("requests = %d, want 3", len(bodies))
	}
	if !bytes.Equal(bodies[0], bodies[1]) || !bytes.Equal(bodies[1], bodies[2]) {
		t.Error("request bodies differ between attempts")
	}
	for i, a := range auths {
		if a != "Bearer ht_abc_def" {
			t.Errorf("request %d Authorization = %q, want %q", i, a, "Bearer ht_abc_def")
		}
	}
	if fmt.Sprint(*waits) != fmt.Sprint([]time.Duration{7 * time.Second, 7 * time.Second}) {
		t.Errorf("waits = %v, want [7s 7s]", *waits)
	}
}

func TestMaxUploadDuration(t *testing.T) {
	if got := MaxUploadDuration(30 * time.Second); got != 150*time.Second {
		t.Errorf("MaxUploadDuration(30s) = %v, want 150s", got)
	}
}

func TestSleepCtxReturnsOnCancel(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	start := time.Now()
	err := sleepCtx(ctx, time.Hour)
	if !errors.Is(err, context.Canceled) {
		t.Errorf("sleepCtx error = %v, want context.Canceled", err)
	}
	if d := time.Since(start); d >= time.Second {
		t.Errorf("sleepCtx took %v, want < 1s", d)
	}
}

func TestUploadGivesUpAfterThree503s(t *testing.T) {
	var hits atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits.Add(1)
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	c, waits := newRetryClient(t, srv.URL)
	_, err := c.Upload(context.Background(), retryTestScan())
	if !errors.Is(err, ErrServerBusy) {
		t.Fatalf("error = %v, want ErrServerBusy", err)
	}
	if n := hits.Load(); n != 3 {
		t.Errorf("requests = %d, want 3", n)
	}
	if len(*waits) != 2 {
		t.Errorf("waits = %d, want 2", len(*waits))
	}
}

func TestUploadStopsWhenContextEndsDuringWait(t *testing.T) {
	var hits atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits.Add(1)
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	c, _ := newRetryClient(t, srv.URL)
	c.sleep = func(context.Context, time.Duration) error { return context.Canceled }
	_, err := c.Upload(context.Background(), retryTestScan())
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("error = %v, want context.Canceled", err)
	}
	if n := hits.Load(); n != 1 {
		t.Errorf("requests = %d, want 1", n)
	}
}

func TestUploadDoesNotRetryOtherStatuses(t *testing.T) {
	for _, status := range []int{401, 409, 422, 426, 429, 500} {
		var hits atomic.Int32
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			hits.Add(1)
			w.WriteHeader(status)
		}))
		c, _ := newRetryClient(t, srv.URL)
		if _, err := c.Upload(context.Background(), retryTestScan()); err == nil {
			t.Errorf("status %d: want an error", status)
		}
		if n := hits.Load(); n != 1 {
			t.Errorf("status %d: requests = %d, want 1", status, n)
		}
		srv.Close()
	}
}
