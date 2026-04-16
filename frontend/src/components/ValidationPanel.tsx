import { useState, useEffect } from "react";
import {
  fetchAssessmentValidation,
  type AssessmentValidation,
  type ValidationIssue,
} from "../api/assessmentValidation";
import "./ValidationPanel.css";

const SEVERITY_LABEL: Record<string, string> = {
  error: "Error",
  warning: "Warning",
  info: "Info",
};

const SEVERITY_CLASS: Record<string, string> = {
  error: "vp-issue--error",
  warning: "vp-issue--warning",
  info: "vp-issue--info",
};

function ScoreBadge({ score }: { score: number }) {
  const cls =
    score >= 80 ? "vp-score--good" : score >= 50 ? "vp-score--fair" : "vp-score--poor";
  return (
    <span className={`vp-score ${cls}`} title="Assessment quality score (0–100)">
      {Math.round(score)}/100
    </span>
  );
}

function IssueRow({ issue }: { issue: ValidationIssue }) {
  return (
    <li className={`vp-issue ${SEVERITY_CLASS[issue.severity] ?? ""}`}>
      <span className="vp-issue-badge">{SEVERITY_LABEL[issue.severity] ?? issue.severity}</span>
      <span className="vp-issue-message">{issue.message}</span>
      {issue.suggestion && (
        <span className="vp-issue-suggestion">{issue.suggestion}</span>
      )}
    </li>
  );
}

export default function ValidationPanel() {
  const [data, setData] = useState<AssessmentValidation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    setLoading(true);
    fetchAssessmentValidation(ac.signal)
      .then((d) => {
        setData(d);
        setError("");
        // Auto-expand if there are errors
        if (d.issue_counts.error > 0) setExpanded(true);
      })
      .catch((err) => {
        if (!ac.signal.aborted)
          setError(err instanceof Error ? err.message : "Failed to load validation");
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, []);

  if (loading) return null;
  if (error) return null; // Non-blocking — silently hide on error

  if (!data) return null;

  const totalIssues =
    data.issue_counts.error + data.issue_counts.warning + data.issue_counts.info;

  const summaryParts: string[] = [];
  if (data.issue_counts.error > 0)
    summaryParts.push(`${data.issue_counts.error} error${data.issue_counts.error > 1 ? "s" : ""}`);
  if (data.issue_counts.warning > 0)
    summaryParts.push(`${data.issue_counts.warning} warning${data.issue_counts.warning > 1 ? "s" : ""}`);
  if (data.issue_counts.info > 0)
    summaryParts.push(`${data.issue_counts.info} tip${data.issue_counts.info > 1 ? "s" : ""}`);

  const summaryText =
    totalIssues === 0
      ? "No issues found — your profile looks complete."
      : summaryParts.join(", ");

  const errorIssues = data.issues.filter((i) => i.severity === "error");
  const warningIssues = data.issues.filter((i) => i.severity === "warning");
  const infoIssues = data.issues.filter((i) => i.severity === "info");

  return (
    <section className="vp-panel settings-section">
      <div className="vp-header" onClick={() => setExpanded((v) => !v)} role="button" tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setExpanded((v) => !v)}>
        <div className="vp-header-left">
          <h2 className="vp-title">Assessment Quality</h2>
          <span className="vp-summary">{summaryText}</span>
        </div>
        <div className="vp-header-right">
          <ScoreBadge score={data.score} />
          <span className="vp-chevron">{expanded ? "▲" : "▼"}</span>
        </div>
      </div>

      {expanded && totalIssues > 0 && (
        <div className="vp-body">
          {errorIssues.length > 0 && (
            <div className="vp-group">
              <h3 className="vp-group-title vp-group-title--error">Errors</h3>
              <ul className="vp-issue-list">
                {errorIssues.map((issue, idx) => (
                  <IssueRow key={idx} issue={issue} />
                ))}
              </ul>
            </div>
          )}
          {warningIssues.length > 0 && (
            <div className="vp-group">
              <h3 className="vp-group-title vp-group-title--warning">Warnings</h3>
              <ul className="vp-issue-list">
                {warningIssues.map((issue, idx) => (
                  <IssueRow key={idx} issue={issue} />
                ))}
              </ul>
            </div>
          )}
          {infoIssues.length > 0 && (
            <div className="vp-group">
              <h3 className="vp-group-title vp-group-title--info">Tips</h3>
              <ul className="vp-issue-list">
                {infoIssues.map((issue, idx) => (
                  <IssueRow key={idx} issue={issue} />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {expanded && totalIssues === 0 && (
        <div className="vp-body vp-body--empty">
          <span className="vp-all-clear">✓ All validation checks passed.</span>
        </div>
      )}
    </section>
  );
}
