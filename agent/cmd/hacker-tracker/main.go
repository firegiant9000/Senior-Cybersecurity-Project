// Command hacker-tracker is the read-only Linux host scanner (Month 4 Phase 4).
//
// It collects an inventory of installed packages, running services, and
// (optionally) listening ports, then either prints it, writes it to a file, or
// uploads it to the Hacker Tracker backend under a per-host enrollment token.
//
// Usage:
//
//	hacker-tracker scan --print
//	hacker-tracker scan --output inventory.json
//	hacker-tracker scan --upload --server https://api.example.com --api-key ht_xxx_yyy
//	hacker-tracker scan --include-ports --print
//
// READ-ONLY: the scanner never reads file contents, secrets, env vars, browser
// history, or documents. See agent/README.md for the full disclosure.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/firegiant9000/hacker-tracker/agent/internal/collectors"
	"github.com/firegiant9000/hacker-tracker/agent/internal/output"
	"github.com/firegiant9000/hacker-tracker/agent/internal/upload"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) == 0 || args[0] == "-h" || args[0] == "--help" {
		usage()
		return nil
	}
	switch args[0] {
	case "scan":
		return runScan(args[1:])
	case "version":
		fmt.Printf("hacker-tracker %s (schema %s)\n", output.ScannerVersion, output.SchemaVersion)
		return nil
	default:
		usage()
		return fmt.Errorf("unknown command %q", args[0])
	}
}

func usage() {
	fmt.Fprint(os.Stderr, `hacker-tracker — read-only Linux host scanner

Commands:
  scan       Collect inventory and print / write / upload it
  version    Print scanner and schema version

Run "hacker-tracker scan --help" for scan flags.
`)
}

func runScan(args []string) error {
	fs := flag.NewFlagSet("scan", flag.ContinueOnError)
	var (
		doPrint      = fs.Bool("print", false, "print the collected inventory as JSON to stdout (default if no action given)")
		outPath      = fs.String("output", "", "write the collected inventory JSON to this file")
		doUpload     = fs.Bool("upload", false, "upload the inventory to the backend")
		includePorts = fs.Bool("include-ports", false, "also collect listening TCP/UDP ports (requires `ss`)")
		server       = fs.String("server", envOr("HT_SERVER", ""), "backend base URL, e.g. https://api.example.com (env HT_SERVER)")
		apiKey       = fs.String("api-key", envOr("HT_API_KEY", ""), "agent enrollment token ht_<prefix>_<secret> (env HT_API_KEY)")
		timeout      = fs.Duration("timeout", 30*time.Second, "HTTP timeout for upload/poll")
	)
	if err := fs.Parse(args); err != nil {
		return err
	}

	// Default action: if the operator gave no sink, --print so the command is
	// never silently a no-op.
	if !*doPrint && *outPath == "" && !*doUpload {
		*doPrint = true
	}

	scan, warnings := collect(*includePorts)
	for _, w := range warnings {
		fmt.Fprintf(os.Stderr, "warning: %s\n", w)
	}

	if *doPrint {
		if err := scan.Write(os.Stdout); err != nil {
			return err
		}
	}
	if *outPath != "" {
		if err := writeFile(*outPath, scan); err != nil {
			return err
		}
		fmt.Fprintf(os.Stderr, "wrote %s\n", *outPath)
	}
	if *doUpload {
		return uploadScan(scan, *server, *apiKey, *timeout)
	}
	return nil
}

// collect runs every collector and assembles the frozen-schema scan plus any
// non-fatal warnings (e.g. unsupported distro) for the operator.
func collect(includePorts bool) (output.Scan, []string) {
	var warnings []string

	host := collectors.CollectHost()

	swResult, err := collectors.CollectSoftware()
	if err != nil {
		warnings = append(warnings, fmt.Sprintf("software collection failed: %v", err))
	}
	if swResult.PackageManager == "" {
		warnings = append(warnings,
			"no supported package manager found (dpkg or rpm) — software list is empty; "+
				"only Debian/Ubuntu (dpkg) and RHEL/Fedora (rpm) are supported in this version")
	}

	services := collectors.CollectServices()

	var ports []output.Port
	if includePorts {
		ports = collectors.CollectPorts()
	}

	scanID, nonce := newScanID(), newNonce()
	return output.New(scanID, nonce, host, swResult.Software, services, ports), warnings
}

func uploadScan(scan output.Scan, server, apiKey string, timeout time.Duration) error {
	if server == "" {
		return errors.New("--server (or HT_SERVER) is required to upload")
	}
	if apiKey == "" {
		return errors.New("--api-key (or HT_API_KEY) is required to upload")
	}
	client := upload.New(server, apiKey, timeout)
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	acc, err := client.Upload(ctx, scan)
	if err != nil {
		if errors.Is(err, upload.ErrUpgradeRequired) {
			return fmt.Errorf("%w — download a newer scanner build and re-run", err)
		}
		return err
	}
	fmt.Printf("uploaded: scan_run #%d (status=%s, assets=%d, software=%d)\n",
		acc.ScanRunID, acc.Status, acc.AssetCount, acc.SoftwareCount)

	// Politely poll a few times so the operator sees the matcher progress
	// without hammering the endpoint. The matcher runs off the request path,
	// so a terminal status here is best-effort, not guaranteed.
	pollStatus(client, acc.ScanRunID, timeout)
	return nil
}

func pollStatus(client *upload.Client, scanRunID int, timeout time.Duration) {
	for i := 0; i < 3; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), timeout)
		status, err := client.PollStatus(ctx, scanRunID)
		cancel()
		if err != nil {
			fmt.Fprintf(os.Stderr, "status poll failed: %v\n", err)
			return
		}
		fmt.Printf("scan_run #%d status: %s\n", scanRunID, status)
		if status == "succeeded" || status == "failed" {
			return
		}
		time.Sleep(2 * time.Second)
	}
	fmt.Println("findings are computed asynchronously — check the dashboard shortly")
}

func writeFile(path string, scan output.Scan) error {
	b, err := scan.Marshal()
	if err != nil {
		return err
	}
	// 0600: the inventory describes the host; keep it owner-readable only.
	return os.WriteFile(path, append(b, '\n'), 0o600)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// newScanID returns a RFC-4122 v4 UUID string (the backend treats scan_id as an
// opaque UUID for replay detection).
func newScanID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		// crypto/rand failure is unrecoverable for a security tool; surface it
		// rather than emitting a predictable id.
		panic("hacker-tracker: cannot read system randomness: " + err.Error())
	}
	b[6] = (b[6] & 0x0f) | 0x40 // version 4
	b[8] = (b[8] & 0x3f) | 0x80 // variant 10
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}

// newNonce returns a 16-byte random hex string, fresh per upload attempt so a
// retried scan with the same scan_id still presents a distinct (scan_id, nonce)
// pair where intended.
func newNonce() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic("hacker-tracker: cannot read system randomness: " + err.Error())
	}
	return hex.EncodeToString(b[:])
}
