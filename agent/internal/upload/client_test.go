package upload

import (
	"context"
	"errors"
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
