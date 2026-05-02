import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { fetchExecutiveSummary, type ExecutiveSummary } from '../api/executiveSummary';
import { fetchLossProjection, type LossProjection } from '../api/lossProjection';
import { fetchFindings, type FindingsReport, type Finding } from '../api/findings';
import { fmtLoss } from '../utils/fmtLoss';
import './ExecutiveReportPage.css';

const SEVERITY_RANK: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
  info: 0,
};

function rankFinding(f: Finding): number {
  const s = (f.severity || '').toLowerCase();
  return f.severity_score ?? SEVERITY_RANK[s] ?? 0;
}

const ExecutiveReportPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [loss, setLoss] = useState<LossProjection | null>(null);
  const [findings, setFindings] = useState<FindingsReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoPrintTriggered, setAutoPrintTriggered] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);

    Promise.allSettled([
      fetchExecutiveSummary(ctrl.signal),
      fetchLossProjection(ctrl.signal),
      fetchFindings(ctrl.signal),
    ])
      .then(([sumRes, lossRes, findRes]) => {
        // Skip state writes if this effect run was already aborted (React 18
        // strict-mode mounts the effect twice in dev; without this gate the
        // first run's .finally flips loading=false before the second run's
        // fetch resolves, briefly rendering "Unable to generate report").
        if (ctrl.signal.aborted) return;
        if (sumRes.status === 'fulfilled') setSummary(sumRes.value);
        else if (sumRes.reason?.name !== 'AbortError') {
          setError(String(sumRes.reason?.message ?? sumRes.reason));
        }
        if (lossRes.status === 'fulfilled') setLoss(lossRes.value);
        if (findRes.status === 'fulfilled') setFindings(findRes.value);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });

    return () => ctrl.abort();
  }, []);

  // Force the printable document to render in light mode regardless of the
  // user's dashboard theme preference. Restore the prior theme on unmount.
  useEffect(() => {
    const html = document.documentElement;
    const prev = html.getAttribute('data-theme');
    html.setAttribute('data-theme', 'light');
    return () => {
      if (prev) html.setAttribute('data-theme', prev);
      else html.removeAttribute('data-theme');
    };
  }, []);

  useEffect(() => {
    if (!loading && !error && summary && !autoPrintTriggered) {
      const params = new URLSearchParams(window.location.search);
      if (params.get('autoprint') === '1') {
        setAutoPrintTriggered(true);
        const t = setTimeout(() => window.print(), 400);
        return () => clearTimeout(t);
      }
    }
  }, [loading, error, summary, autoPrintTriggered]);

  const generatedDate = useMemo(() => {
    const iso = summary?.generated_at ?? new Date().toISOString();
    return new Date(iso).toLocaleString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  }, [summary?.generated_at]);

  const topFindings = useMemo(() => {
    if (!findings?.findings?.length) return [];
    return [...findings.findings].sort((a, b) => rankFinding(b) - rankFinding(a)).slice(0, 5);
  }, [findings]);

  if (loading) {
    return (
      <div className="exec-report-shell">
        <p className="exec-report-status">Generating executive report…</p>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="exec-report-shell">
        <p className="exec-report-status exec-report-status--error">
          Unable to generate report{error ? `: ${error}` : '.'}
        </p>
      </div>
    );
  }

  return (
    <div className="exec-report-shell">
      <div className="exec-report-toolbar">
        <button
          type="button"
          className="exec-report-print-btn"
          onClick={() => window.print()}
        >
          Print / Save as PDF
        </button>
        <button
          type="button"
          className="exec-report-back-btn"
          onClick={() => {
            // Try to close (works if this tab was script-opened from the
            // dashboard); otherwise fall back to in-app navigation so we
            // don't tear down SPA state with a full reload.
            window.close();
            navigate('/dashboard');
          }}
        >
          Close
        </button>
      </div>

      <article className="exec-report-document">
        <header className="exec-report-header">
          <div className="exec-report-title-block">
            <span className="exec-report-eyebrow">Cyber Risk Executive Report</span>
            <h1 className="exec-report-title">Risk &amp; Loss Snapshot</h1>
            <span className="exec-report-subtitle">Small-Business Threat Landscape · {summary.data_year_range}</span>
          </div>
          <div className="exec-report-meta">
            <div><strong>Generated:</strong> {generatedDate}</div>
            {user?.email && <div><strong>Prepared for:</strong> {user.email}</div>}
            <div><strong>Confidence:</strong> {summary.confidence_level}</div>
          </div>
        </header>

        {/* Risk Snapshot */}
        <section className="exec-report-section">
          <h2 className="exec-report-section-title">Risk Snapshot</h2>
          <div className="exec-report-risk-row">
            <div className="exec-report-risk-score">
              <span className="exec-report-risk-score-value">{summary.risk_score}</span>
              <span className={`exec-report-risk-pill exec-report-risk-pill--${summary.risk_label}`}>
                {summary.risk_label}
              </span>
            </div>
            <div className="exec-report-metric-grid">
              <div className="exec-report-metric">
                <div className="exec-report-metric-label">Reported Cyber Losses · {summary.data_year_range}</div>
                <div className="exec-report-metric-value">{summary.loss_estimate_formatted}</div>
                <div className="exec-report-metric-sub">FBI IC3 historical sum (all sectors)</div>
              </div>
              <div className="exec-report-metric">
                <div className="exec-report-metric-label">Vulnerabilities Actively Exploited</div>
                <div className="exec-report-metric-value">{summary.kev_count.toLocaleString()}</div>
                <div className="exec-report-metric-sub">CISA KEV catalog</div>
              </div>
              <div className="exec-report-metric">
                <div className="exec-report-metric-label">Critical CVEs in the Wild</div>
                <div className="exec-report-metric-value">{summary.critical_cve_count.toLocaleString()}</div>
                <div className="exec-report-metric-sub">NVD critical-severity</div>
              </div>
            </div>
          </div>
        </section>

        {/* Top threats */}
        {summary.top_threats.length > 0 && (
          <section className="exec-report-section">
            <h2 className="exec-report-section-title">Most Costly Attack Types</h2>
            <table className="exec-report-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Attack Type</th>
                  <th style={{ width: 120 }}>Complaints</th>
                  <th style={{ width: 140 }}>Total Loss</th>
                </tr>
              </thead>
              <tbody>
                {summary.top_threats.map((t, i) => (
                  <tr key={t.name}>
                    <td>{i + 1}</td>
                    <td>{t.name}</td>
                    <td>{t.complaint_count.toLocaleString()}</td>
                    <td>{fmtLoss(t.total_loss)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Projected loss */}
        {loss?.has_data && (
          <section className="exec-report-section">
            <h2 className="exec-report-section-title">Projected Annual Loss</h2>
            <div className="exec-report-loss-row">
              <div className="exec-report-loss-headline">
                <span className="exec-report-loss-value">{loss.projected_annual_loss_formatted}</span>
                <span className="exec-report-loss-context">
                  {loss.sector || 'national average'}
                  {loss.state ? ` · ${loss.state}` : ''}
                  {loss.employee_range ? ` · ${loss.employee_range}` : ''}
                </span>
                <span className="exec-report-loss-confidence">Confidence: {loss.confidence_level}</span>
              </div>
              <ul className="exec-report-loss-meta">
                {loss.ic3_data_years && <li><strong>Years included:</strong> {loss.ic3_data_years}</li>}
                {loss.ic3_incident_count != null && (
                  <li><strong>IC3 incidents in sample:</strong> {loss.ic3_incident_count.toLocaleString()}</li>
                )}
                {loss.ic3_avg_loss_per_incident != null && (
                  <li>
                    <strong>Avg loss per incident:</strong>{' '}
                    ${loss.ic3_avg_loss_per_incident.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </li>
                )}
                <li><strong>Size multiplier:</strong> ×{loss.size_multiplier}</li>
              </ul>
              <p className="exec-report-loss-method">{loss.methodology}</p>
            </div>
          </section>
        )}

        {/* Top findings */}
        {topFindings.length > 0 && (
          <section className="exec-report-section">
            <h2 className="exec-report-section-title">Top Findings</h2>
            <ol className="exec-report-findings-list">
              {topFindings.map((f) => (
                <li key={f.id} className="exec-report-finding">
                  <div className="exec-report-finding-head">
                    <span className={`exec-report-severity exec-report-severity--${(f.severity || 'info').toLowerCase()}`}>
                      {f.severity}
                    </span>
                    <span className="exec-report-finding-title">{f.title}</span>
                  </div>
                  <p className="exec-report-finding-desc">{f.description}</p>
                  {f.affected_assets?.length > 0 && (
                    <div className="exec-report-finding-assets">
                      <strong>Affected:</strong> {f.affected_assets.slice(0, 4).join(', ')}
                      {f.affected_assets.length > 4 ? ` +${f.affected_assets.length - 4} more` : ''}
                    </div>
                  )}
                </li>
              ))}
            </ol>
            {findings && (
              <p className="exec-report-findings-meta">
                Total findings: {findings.summary.total} · Assessment tier: {findings.assessment_tier}
              </p>
            )}
          </section>
        )}

        {/* Methodology */}
        <section className="exec-report-section">
          <h2 className="exec-report-section-title">Methodology</h2>
          <p className="exec-report-methodology">{summary.methodology}</p>
        </section>

        {/* Disclaimer footer */}
        <footer className="exec-report-footer">
          <p className="exec-report-disclaimer">{summary.disclaimer}</p>
          <p className="exec-report-footer-meta">
            Hacker Tracker · Cyber Threat Intelligence &amp; Anomaly Detection Platform · Generated {generatedDate}
          </p>
        </footer>
      </article>
    </div>
  );
};

export default ExecutiveReportPage;
