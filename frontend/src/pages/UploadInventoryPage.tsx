import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  CsvPreviewResponse,
  ScanRun,
  ScanRunDiff,
  getScanRun,
  getScanRunDiff,
  importInventoryCsv,
  previewInventoryCsv,
  rollbackScanRun,
} from "../api/inventory";
import { logActivationEvent } from "../api/analytics";
import "../Dashboard.css";

/**
 * Month 2 Phase C: CSV inventory upload page.
 *
 * Drag-drop a CSV (or click to pick), preview it (no DB write), then
 * confirm to import. After import the page polls the scan_run until it
 * reaches a terminal state.
 */
export default function UploadInventoryPage() {
  const { orgId } = useAuth();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<CsvPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [scanRun, setScanRun] = useState<ScanRun | null>(null);
  const [diff, setDiff] = useState<ScanRunDiff | null>(null);
  const [rollingBack, setRollingBack] = useState(false);
  const [rolledBack, setRolledBack] = useState(false);
  const [error, setError] = useState("");

  const reset = () => {
    setFile(null);
    setPreview(null);
    setScanRun(null);
    setDiff(null);
    setRolledBack(false);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleRollback = useCallback(async () => {
    if (!orgId || !scanRun) return;
    if (
      !window.confirm(
        `Roll back import #${scanRun.id}? This deletes any asset/software rows this upload created. Rows that pre-existed and were refreshed are not reverted.`,
      )
    ) {
      return;
    }
    setRollingBack(true);
    try {
      await rollbackScanRun(orgId, scanRun.id);
      setRolledBack(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRollingBack(false);
    }
  }, [orgId, scanRun]);

  const handleFile = (f: File | null) => {
    setError("");
    setPreview(null);
    setScanRun(null);
    setFile(f);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  const handlePreview = useCallback(async () => {
    if (!file || !orgId) return;
    setPreviewLoading(true);
    setError("");
    try {
      const result = await previewInventoryCsv(orgId, file);
      setPreview(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  }, [file, orgId]);

  const handleImport = useCallback(async () => {
    if (!file || !orgId) return;
    setImporting(true);
    setError("");
    void logActivationEvent({
      event_type: "csv_upload_started",
      org_id: orgId,
      payload: { size_kb: Math.round(file.size / 1024) },
    });
    try {
      const run = await importInventoryCsv(orgId, file);
      setScanRun(run);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setImporting(false);
    }
  }, [file, orgId]);

  useEffect(() => {
    if (scanRun?.status === "succeeded") {
      void logActivationEvent({
        event_type: "csv_upload_completed",
        org_id: orgId ?? null,
        payload: {
          scan_run_id: scanRun.id,
          asset_count: scanRun.asset_count,
          software_count: scanRun.software_count,
        },
      });
      if (orgId) {
        getScanRunDiff(orgId, scanRun.id)
          .then(setDiff)
          .catch(() => setDiff(null));
      }
    }
  }, [scanRun?.id, scanRun?.status, scanRun?.asset_count, scanRun?.software_count, orgId]);

  // Poll the scan run until terminal — guards against the import endpoint
  // returning before the background match work would have finished.
  useEffect(() => {
    if (!scanRun || !orgId) return;
    if (scanRun.status === "succeeded" || scanRun.status === "failed" || scanRun.status === "partial") {
      return;
    }
    const handle = window.setInterval(async () => {
      try {
        const fresh = await getScanRun(orgId, scanRun.id);
        setScanRun(fresh);
        if (fresh.status === "succeeded" || fresh.status === "failed" || fresh.status === "partial") {
          window.clearInterval(handle);
        }
      } catch {
        window.clearInterval(handle);
      }
    }, 2000);
    return () => window.clearInterval(handle);
  }, [scanRun, orgId]);

  const kevMatches =
    scanRun?.metadata && typeof (scanRun.metadata as { kev_matches?: number }).kev_matches === "number"
      ? (scanRun.metadata as { kev_matches: number }).kev_matches
      : null;

  return (
    <div className="dashboard-page" style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h1>Upload asset inventory</h1>
      <p style={{ color: "#555" }}>
        Upload a CSV of your assets and installed software. The columns we expect are documented in{" "}
        <a href="/sample-inventory.csv" download>
          the sample CSV
        </a>
        . Re-uploading is safe — duplicate hostnames refresh existing rows
        rather than creating new ones.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? "#3b82f6" : "#cbd5e1"}`,
          borderRadius: 8,
          padding: 32,
          textAlign: "center",
          cursor: "pointer",
          background: dragging ? "#eff6ff" : "#f8fafc",
          marginBottom: 16,
        }}
      >
        {file ? (
          <div>
            <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
            <div style={{ marginTop: 8 }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  reset();
                }}
                type="button"
              >
                Choose a different file
              </button>
            </div>
          </div>
        ) : (
          <>
            <div style={{ fontSize: 16, marginBottom: 8 }}>
              Drag a CSV here, or click to pick one
            </div>
            <div style={{ fontSize: 13, color: "#64748b" }}>
              Max 10,000 rows. UTF-8 encoded.
            </div>
          </>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          style={{ display: "none" }}
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        />
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          onClick={handlePreview}
          disabled={!file || previewLoading || importing || !!scanRun}
        >
          {previewLoading ? "Validating…" : "Preview"}
        </button>
        <button
          type="button"
          onClick={handleImport}
          disabled={!preview || preview.valid_rows === 0 || importing || !!scanRun}
        >
          {importing ? "Importing…" : "Import"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", color: "#991b1b", padding: 12, borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {preview && !scanRun && (
        <div style={{ background: "#f1f5f9", padding: 16, borderRadius: 6, marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Preview</h3>
          <ul>
            <li>
              <strong>{preview.valid_rows}</strong> valid rows
            </li>
            <li>
              <strong>{preview.distinct_assets}</strong> distinct assets
              {" — "}
              {preview.would_create} new, {preview.would_update} refreshed
            </li>
            <li>
              <strong>{preview.distinct_software}</strong> software entries
            </li>
            {preview.invalid_rows.length > 0 && (
              <li>
                <strong>{preview.invalid_rows.length}</strong> warnings / errors
              </li>
            )}
          </ul>
          {preview.invalid_rows.length > 0 && (
            <details>
              <summary>Show warnings</summary>
              <ul style={{ maxHeight: 200, overflowY: "auto" }}>
                {preview.invalid_rows.slice(0, 50).map((row) => (
                  <li key={row.row_number}>
                    Row {row.row_number}: {row.errors.join("; ")}
                  </li>
                ))}
                {preview.invalid_rows.length > 50 && (
                  <li>… and {preview.invalid_rows.length - 50} more</li>
                )}
              </ul>
            </details>
          )}
        </div>
      )}

      {scanRun && (
        <div style={{ background: "#ecfdf5", padding: 16, borderRadius: 6, marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Import #{scanRun.id}</h3>
          <ul>
            <li>
              Status: <strong>{scanRun.status}</strong>
            </li>
            <li>
              Assets: <strong>{scanRun.asset_count}</strong>
            </li>
            <li>
              Software entries: <strong>{scanRun.software_count}</strong>
            </li>
            {kevMatches !== null && (
              <li>
                KEV matches (preliminary literal match):{" "}
                <strong>{kevMatches}</strong>
              </li>
            )}
            {scanRun.error_message && (
              <li style={{ color: "#991b1b" }}>{scanRun.error_message}</li>
            )}
          </ul>
          <p style={{ fontSize: 13, color: "#475569" }}>
            KEV matches are a preliminary literal vendor+product match. The
            Month 3 CPE matcher will refine these.
          </p>
          {diff && !rolledBack && (
            <div
              style={{
                marginTop: 8,
                padding: 10,
                background: "#eff6ff",
                borderRadius: 6,
                fontSize: 13,
              }}
            >
              <strong>Diff vs previous upload:</strong>{" "}
              {diff.assets_added} new asset{diff.assets_added === 1 ? "" : "s"},{" "}
              {diff.assets_refreshed} refreshed, {diff.software_added} new
              software entries.
              {diff.previous_scan_run_id !== null && (
                <span style={{ color: "#475569" }}>
                  {" "}
                  (prior run #{diff.previous_scan_run_id})
                </span>
              )}
            </div>
          )}
          {rolledBack && (
            <div
              style={{
                marginTop: 8,
                padding: 10,
                background: "#fef2f2",
                color: "#991b1b",
                borderRadius: 6,
                fontSize: 13,
              }}
            >
              Rolled back. Rows this upload created have been removed.
            </div>
          )}
          <Link to="/assets">View assets →</Link>
          <span style={{ margin: "0 12px" }}>·</span>
          <button type="button" onClick={reset}>
            Upload another
          </button>
          {scanRun.status === "succeeded" && !rolledBack && (
            <>
              <span style={{ margin: "0 12px" }}>·</span>
              <button
                type="button"
                onClick={handleRollback}
                disabled={rollingBack}
                style={{ color: "#991b1b" }}
              >
                {rollingBack ? "Rolling back…" : "Undo last upload"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
