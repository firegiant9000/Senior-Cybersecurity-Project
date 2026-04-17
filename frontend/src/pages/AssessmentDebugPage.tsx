import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useDarkMode } from "../hooks/useDarkMode";
import {
  fetchAssessmentDebug,
  type DebugAssessmentResponse,
  type FindingsReadinessBlock,
} from "../api/assessmentDebug";
import {
  fetchAISummaryHistory,
  fetchAISummaryGeneration,
  type AISummaryGenerationDetail,
  type AISummaryGenerationListResponse,
} from "../api/aiSummaryHistory";
import type { AssessmentValidation } from "../api/assessmentValidation";
import type { FindingsReport } from "../api/findings";
import "../Dashboard.css";
import "./SettingsPage.css";

export default function AssessmentDebugPage() {
  const { role, orgRole, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  useDarkMode();

  const [data, setData] = useState<DebugAssessmentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const canAccess =
    role === "admin" || orgRole === "admin" || orgRole === "owner";

  useEffect(() => {
    if (authLoading) return;
    if (!canAccess) {
      navigate("/settings");
      return;
    }
    const ac = new AbortController();
    setLoading(true);
    fetchAssessmentDebug(ac.signal)
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Failed to load debug data");
        }
      })
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, [authLoading, canAccess, navigate]);

  if (authLoading) return null;
  if (!canAccess) return null;

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Assessment Debug View</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
          <button type="button" onClick={() => navigate("/settings")}>
            Back to Settings
          </button>
        </div>
      </header>

      <div className="settings-page settings-page--embedded">
        <div className="settings-card settings-card--wide">
          {loading && <p className="settings-loading">Loading debug snapshot…</p>}
          {error && <div className="settings-error">{error}</div>}

          {!loading && !error && data && (
            <div className="settings-sections">
              <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem", fontSize: "0.85rem" }}>
                Snapshot generated at {new Date(data.generated_at).toLocaleString()} · Org #{data.org_id}
              </p>

              <RawProfileSection profile={data.raw_profile} />
              <IntakeSection intake={data.intake} />
              <ValidationSection validation={data.validation} />
              <FindingsSection readiness={data.findings_readiness} />
              <SummaryHistorySection />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RawProfileSection({ profile }: { profile: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);

  return (
    <section className="settings-section">
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <h2>Raw Inputs</h2>
        <button
          type="button"
          className="action-btn"
          onClick={() => setOpen((o) => !o)}
          style={{ fontSize: "0.8rem", padding: "0.25rem 0.75rem" }}
        >
          {open ? "Collapse" : "Expand"}
        </button>
      </div>
      <div
        className="settings-field"
        style={{ background: "var(--card-bg, #1a1a2e)", borderRadius: 4, padding: "0.25rem 0.5rem" }}
      >
        <span className="role-badge" style={{ background: "#c0392b" }}>
          PII Warning — visible to org admins and owners only
        </span>
      </div>
      {open && (
        <table className="vendor-table" style={{ marginTop: "0.75rem" }}>
          <thead>
            <tr>
              <th>Field</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(profile).map(([key, val]) => (
              <tr key={key}>
                <td style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>{key}</td>
                <td style={{ fontFamily: "monospace", fontSize: "0.85rem", wordBreak: "break-all" }}>
                  {val === null || val === undefined
                    ? <span style={{ color: "var(--text-muted)" }}>null</span>
                    : typeof val === "object"
                    ? <CollapsedJson value={val} />
                    : String(val)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function CollapsedJson({ value }: { value: unknown }) {
  const [open, setOpen] = useState(false);
  return (
    <span>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{ background: "none", border: "none", cursor: "pointer", color: "var(--accent, #00d4ff)", fontSize: "0.8rem", padding: 0 }}
      >
        {open ? "▾ hide" : "▸ show"}
      </button>
      {open && (
        <pre style={{ margin: "0.25rem 0 0", fontSize: "0.78rem", whiteSpace: "pre-wrap" }}>
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </span>
  );
}

function IntakeSection({ intake }: { intake: DebugAssessmentResponse["intake"] }) {
  const tierColors: Record<string, string> = {
    incomplete: "#e74c3c",
    basic: "#f39c12",
    enhanced: "#27ae60",
    comprehensive: "#2980b9",
  };
  const color = tierColors[intake.current_tier] ?? "#888";

  return (
    <section className="settings-section">
      <h2>Normalized Profile &amp; Tier Progress</h2>
      <div className="settings-field">
        <label>Current Tier</label>
        <span className="role-badge" style={{ background: color }}>
          {intake.current_tier}
        </span>
      </div>
      {intake.next_tier && (
        <div className="settings-field">
          <label>Progress to {intake.next_tier}</label>
          <span>{intake.next_tier_progress.toFixed(1)}%</span>
        </div>
      )}
      {intake.fields_to_advance.length > 0 && (
        <div className="settings-field" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.5rem" }}>
          <label>Fields to advance</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
            {intake.fields_to_advance.map((f) => (
              <span key={f} className="role-badge" style={{ background: "#555" }}>{f}</span>
            ))}
          </div>
        </div>
      )}
      {intake.tiers.map((tier) => (
        <details key={tier.tier} style={{ marginTop: "0.5rem" }}>
          <summary style={{ cursor: "pointer", fontSize: "0.9rem", color: "var(--text-primary, #1e293b)" }}>
            <span className="role-badge" style={{ background: tier.all_met ? "#27ae60" : "#555" }}>
              {tier.tier}
            </span>{" "}
            {tier.label} — {tier.all_met ? "✓ met" : "not met"}
          </summary>
          <ul style={{ marginTop: "0.5rem", paddingLeft: "1.25rem", fontSize: "0.85rem" }}>
            {tier.requirements.map((req) => (
              <li key={req.key} style={{ color: req.met ? "var(--text-muted)" : "inherit" }}>
                {req.met ? "✓" : "✗"} {req.label}
                {req.detail && <span style={{ color: "var(--text-muted)", marginLeft: "0.5rem" }}>{req.detail}</span>}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </section>
  );
}

function ValidationSection({ validation }: { validation: AssessmentValidation }) {
  const severityColor = { error: "#e74c3c", warning: "#f39c12", info: "#3498db" };

  return (
    <section className="settings-section">
      <h2>Validation</h2>
      <div className="settings-field">
        <label>Quality Score</label>
        <span>{validation.score.toFixed(1)} / 100</span>
      </div>
      <div className="settings-field">
        <label>Status</label>
        <span className={`status-badge ${validation.passed ? "active" : "inactive"}`}>
          {validation.passed ? "Passed" : "Failed"}
        </span>
      </div>
      <div className="settings-field" style={{ gap: "0.5rem" }}>
        <label>Issue counts</label>
        {(Object.entries(validation.issue_counts) as [string, number][]).map(([sev, count]) => (
          <span
            key={sev}
            className="role-badge"
            style={{ background: severityColor[sev as keyof typeof severityColor] ?? "#555" }}
          >
            {sev}: {count}
          </span>
        ))}
      </div>
      {validation.issues.length > 0 && (
        <table className="vendor-table" style={{ marginTop: "0.75rem" }}>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Field</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {validation.issues.map((issue, i) => (
              <tr key={i}>
                <td>
                  <span
                    className="role-badge"
                    style={{ background: severityColor[issue.severity] ?? "#555" }}
                  >
                    {issue.severity}
                  </span>
                </td>
                <td style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>{issue.field}</td>
                <td style={{ fontSize: "0.85rem" }}>
                  {issue.message}
                  {issue.suggestion && (
                    <span style={{ color: "var(--text-muted)", display: "block" }}>
                      Suggestion: {issue.suggestion}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function SummaryHistorySection() {
  const [history, setHistory] = useState<AISummaryGenerationListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<AISummaryGenerationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    fetchAISummaryHistory(ac.signal, 10, 0)
      .then((d) => { setHistory(d); setError(""); })
      .catch((err) => { if (err.name !== "AbortError") setError("Failed to load summary history"); })
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, []);

  function toggleRow(id: number) {
    if (expanded === id) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(id);
    setDetail(null);
    setDetailLoading(true);
    const ac = new AbortController();
    fetchAISummaryGeneration(id, ac.signal)
      .then((d) => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }

  const statusColor: Record<string, string> = {
    success: "#27ae60",
    fallback_used: "#f39c12",
    error: "#e74c3c",
  };

  return (
    <section className="settings-section">
      <h2>Executive Summary History</h2>
      {loading && <p className="settings-loading">Loading history…</p>}
      {error && <div className="settings-error">{error}</div>}
      {!loading && !error && history && history.items.length === 0 && (
        <p className="tech-stack-description" style={{ color: "var(--text-muted)" }}>
          No summary generations recorded yet. Trigger a regeneration to see history.
        </p>
      )}
      {!loading && !error && history && history.items.length > 0 && (
        <>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
            Showing {history.items.length} of {history.total} generations · click a row to inspect
          </p>
          <table className="vendor-table">
            <thead>
              <tr>
                <th>Generated At</th>
                <th>Model</th>
                <th>Source</th>
                <th>Status</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {history.items.map((row) => (
                <>
                  <tr
                    key={row.id}
                    style={{ cursor: "pointer" }}
                    onClick={() => toggleRow(row.id)}
                  >
                    <td style={{ fontSize: "0.85rem" }}>
                      {new Date(row.generated_at).toLocaleString()}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>{row.model_name}</td>
                    <td>
                      <span className="role-badge" style={{ background: "#555" }}>{row.source}</span>
                    </td>
                    <td>
                      <span
                        className="role-badge"
                        style={{ background: statusColor[row.status] ?? "#555" }}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.85rem" }}>
                      {row.latency_ms != null ? `${row.latency_ms} ms` : "—"}
                    </td>
                  </tr>
                  {expanded === row.id && (
                    <tr key={`${row.id}-detail`}>
                      <td colSpan={5} style={{ padding: "0.75rem 1rem", background: "var(--card-bg, #1a1a2e)" }}>
                        {detailLoading && <p style={{ fontSize: "0.85rem" }}>Loading detail…</p>}
                        {row.error_message && (
                          <div className="settings-error" style={{ marginBottom: "0.5rem", fontSize: "0.85rem" }}>
                            Error: {row.error_message}
                          </div>
                        )}
                        {detail && (
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                            {detail.output_text && (
                              <div>
                                <strong style={{ fontSize: "0.85rem" }}>Output Preview</strong>
                                <p style={{ fontSize: "0.82rem", whiteSpace: "pre-wrap", marginTop: "0.25rem", color: "var(--text-muted)" }}>
                                  {detail.output_text.slice(0, 400)}{detail.output_text.length > 400 ? "…" : ""}
                                </p>
                              </div>
                            )}
                            <details>
                              <summary style={{ cursor: "pointer", fontSize: "0.85rem" }}>Prompt Inputs (JSON)</summary>
                              <pre style={{ fontSize: "0.78rem", whiteSpace: "pre-wrap", marginTop: "0.25rem" }}>
                                {JSON.stringify(detail.prompt_inputs, null, 2)}
                              </pre>
                            </details>
                            {detail.rendered_prompt && (
                              <details>
                                <summary style={{ cursor: "pointer", fontSize: "0.85rem" }}>Rendered Prompt</summary>
                                <pre style={{ fontSize: "0.78rem", whiteSpace: "pre-wrap", marginTop: "0.25rem" }}>
                                  {detail.rendered_prompt}
                                </pre>
                              </details>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

function FindingsSection({ readiness }: { readiness: FindingsReadinessBlock }) {
  if (!readiness.ready) {
    return (
      <section className="settings-section">
        <h2>Exposure &amp; Readiness</h2>
        <div className="settings-error" style={{ marginBottom: "0.75rem" }}>
          Not ready: {readiness.blocking_reason}
        </div>
        <p className="tech-stack-description">
          Complete your organization profile to reach Enhanced tier and unlock findings.
        </p>
        <div style={{ marginTop: "0.75rem" }}>
          <a href="/org-profile" className="action-btn" style={{ textDecoration: "none" }}>
            Go to Organization Profile
          </a>
        </div>
      </section>
    );
  }

  const report = readiness.report as FindingsReport;

  return (
    <section className="settings-section">
      <h2>Exposure &amp; Readiness</h2>
      <div className="settings-field">
        <label>Assessment Tier</label>
        <span className="role-badge" style={{ background: "#27ae60" }}>{report.assessment_tier}</span>
      </div>
      <div className="settings-field">
        <label>Total Findings</label>
        <span>{report.summary.total}</span>
      </div>
      <div className="settings-field" style={{ gap: "0.5rem" }}>
        <label>By Severity</label>
        {Object.entries(report.summary.by_severity).map(([sev, count]) => (
          <span key={sev} className="role-badge" style={{ background: "#555" }}>
            {sev}: {count}
          </span>
        ))}
      </div>
      {report.findings.length > 0 && (
        <table className="vendor-table" style={{ marginTop: "0.75rem" }}>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Type</th>
              <th>Title</th>
            </tr>
          </thead>
          <tbody>
            {report.findings.map((f) => (
              <tr key={f.id}>
                <td>
                  <span className="role-badge" style={{ background: "#555" }}>{f.severity}</span>
                </td>
                <td style={{ fontSize: "0.85rem" }}>{f.finding_type}</td>
                <td style={{ fontSize: "0.85rem" }}>{f.title}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
