import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchFindings,
  fetchFindingsHistory,
  patchFindingStatus,
  type FindingsReport,
  type Finding,
  type FindingStatus,
  type SnapshotListItem,
} from '../../api/findings';
import { useAuth } from '../../context/AuthContext';
import { downloadCsv } from '../../utils/csvExport';
import SeverityBadge from '../shared/SeverityBadge';
import DisclaimerBanner from '../shared/DisclaimerBanner';
import InfoTip from '../shared/InfoTip';
import './FindingsTab.css';

const TYPE_LABELS: Record<string, { label: string; icon: string }> = {
  threat_exposure: { label: 'Threats Targeting You', icon: '\u26a0' },
  vendor_exposure: { label: 'Software & Vendor Risks', icon: '\ud83d\udee1' },
  data_gap: { label: 'Missing Information', icon: '\ud83d\udcca' },
  recommended_action: { label: 'What to Do Next', icon: '\u2705' },
};

const TYPE_ORDER = ['threat_exposure', 'vendor_exposure', 'data_gap', 'recommended_action'];

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const LOADING_STAGES = [
  'Checking your email and website security...',
  'Reviewing your security certificates...',
  'Matching known threats to your software...',
  'Identifying software vulnerabilities...',
  'Preparing your security report...',
];

const FindingsLoadingBar: React.FC = () => {
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStageIndex((i) => (i < LOADING_STAGES.length - 1 ? i + 1 : i));
    }, 3500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="tab-page">
      <div className="findings-loading">
        <p className="findings-loading-title">Analyzing your organization&apos;s threat landscape</p>
        <div className="findings-progress-track">
          <div className="findings-progress-fill" />
        </div>
        <p className="findings-loading-stage">{LOADING_STAGES[stageIndex]}</p>
        <p className="findings-loading-sub">This may take 15–30 seconds on first load.</p>
      </div>
    </div>
  );
};

const MIN_LOADING_MS = 1200;

const FindingsTab: React.FC = () => {
  const { user } = useAuth();
  const [report, setReport] = useState<FindingsReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [minLoadingDone, setMinLoadingDone] = useState(false);
  const [error, setError] = useState('');
  const [activeFilter, setActiveFilter] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [history, setHistory] = useState<SnapshotListItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const loadHistory = useCallback(() => {
    if (!user) return;
    const controller = new AbortController();
    fetchFindingsHistory(controller.signal, 10)
      .then((resp) => setHistory(resp.items))
      .catch(() => {});
    return () => controller.abort();
  }, [user]);

  const load = useCallback(() => {
    if (!user) return;
    const controller = new AbortController();
    setLoading(true);
    setMinLoadingDone(false);
    setError('');
    const minTimer = setTimeout(() => setMinLoadingDone(true), MIN_LOADING_MS);
    fetchFindings(controller.signal)
      .then(setReport)
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load findings');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
      clearTimeout(minTimer);
    };
  }, [user]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  useEffect(() => {
    if (showHistory) {
      const cleanup = loadHistory();
      return cleanup;
    }
  }, [showHistory, loadHistory]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const setFindingStatus = useCallback(
    async (finding: Finding, nextStatus: FindingStatus) => {
      // Optimistic local update so the checkbox feels instant.
      setReport((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          findings: prev.findings.map((f) =>
            f.stable_key === finding.stable_key ? { ...f, status: nextStatus } : f,
          ),
        };
      });
      try {
        await patchFindingStatus(finding.stable_key, nextStatus, {
          title: finding.title,
          severity: finding.severity,
        });
        // Notify the rest of the app (risk score widget, exec report) so
        // they can refetch and animate the deduction.
        window.dispatchEvent(
          new CustomEvent('hackertracker:finding-status-changed', {
            detail: { stable_key: finding.stable_key, status: nextStatus },
          }),
        );
      } catch (err) {
        // Revert on failure.
        setReport((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            findings: prev.findings.map((f) =>
              f.stable_key === finding.stable_key
                ? { ...f, status: finding.status }
                : f,
            ),
          };
        });
        setError(err instanceof Error ? err.message : 'Failed to update finding');
      }
    },
    [],
  );

  const grouped = useMemo(() => {
    if (!report) return {};
    const filtered = activeFilter
      ? report.findings.filter((f) => f.finding_type === activeFilter)
      : report.findings;

    const groups: Record<string, Finding[]> = {};
    for (const type of TYPE_ORDER) {
      const items = filtered
        .filter((f) => f.finding_type === type)
        .sort((a, b) => (b.severity_score ?? 0) - (a.severity_score ?? 0));
      if (items.length > 0) groups[type] = items;
    }
    return groups;
  }, [report, activeFilter]);

  if (!user) {
    return <div className="tab-page"><p>Please log in to view findings.</p></div>;
  }

  if (loading || !minLoadingDone) {
    return <FindingsLoadingBar />;
  }

  if (error) {
    const lower = error.toLowerCase();
    const isIncomplete =
      lower.includes('incomplete') ||
      lower.includes('enhanced tier') ||
      lower.includes('profile') && (lower.includes('required') || lower.includes('missing')) ||
      lower.includes('no vendor') ||
      lower.includes('no domain');
    return (
      <div className="tab-page">
        <div className="findings-error-card">
          {isIncomplete ? (
            <>
              <span className="findings-error-icon">{'\ud83d\udccb'}</span>
              <p className="findings-error-title">Setup Required</p>
              <p className="findings-error-detail">
                Complete these steps to unlock your Security Findings report:
              </p>
              <ul className="findings-setup-checklist">
                <li>Organization name</li>
                <li>Industry &amp; state</li>
                <li>At least one vendor (Technology Stack)</li>
                <li>At least one domain</li>
                <li>At least one security question answered</li>
              </ul>
              <Link to="/org-profile" className="findings-error-action">
                Complete Profile
              </Link>
            </>
          ) : (
            <>
              <span className="findings-error-icon">{'\u26a0'}</span>
              <p className="findings-error-title">Couldn't Load Findings</p>
              <p className="findings-error-detail">
                We hit a snag fetching your security findings. This is usually temporary — try again, or check your Organization Profile if the problem persists.
              </p>
              <p className="findings-error-detail" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Details: {error}
              </p>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                <button className="findings-error-action" onClick={load}>
                  Retry
                </button>
                <Link to="/org-profile" className="findings-error-action" style={{ background: 'transparent', color: 'var(--accent)', border: '1px solid var(--accent)' }}>
                  Review Profile
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  if (!report || report.findings.length === 0) {
    return (
      <div className="tab-page">
        <div className="findings-empty-card">
          <span className="findings-empty-icon">{'\ud83c\udf1f'}</span>
          <p className="findings-empty-title">No Findings</p>
          <p className="findings-empty-detail">
            No findings were generated for your organization. This could mean your
            profile data is limited — try adding more vendors and domains in Organization Profile.
          </p>
          <Link to="/org-profile" className="findings-empty-action">
            Update Profile
          </Link>
        </div>
      </div>
    );
  }

  const { summary } = report;
  const generatedDate = new Date(report.generated_at).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
  });

  return (
    <div className="tab-page findings-tab">
      {/* Toolbar */}
      <div className="findings-toolbar">
        <div className="findings-actions">
          <button
            className="overview-refresh-btn"
            onClick={load}
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          <button
            className="export-csv-btn"
            onClick={() =>
              downloadCsv(
                'findings.csv',
                ['Type', 'Severity', 'Score', 'Title', 'Description', 'Source', 'Affected Assets'],
                report.findings.map((f) => [
                  f.finding_type,
                  f.severity,
                  f.severity_score ?? '',
                  f.title,
                  f.description,
                  f.source,
                  f.affected_assets.join('; '),
                ])
              )
            }
            disabled={!report || report.findings.length === 0}
          >
            Download CSV
          </button>
        </div>
        <span className="findings-meta">
          {summary.total} finding{summary.total !== 1 ? 's' : ''} &middot; Generated {generatedDate}
        </span>
      </div>

      {/* Filters + severity on one row */}
      <div className="findings-filter-row">
        <div className="findings-summary-row">
          <button
            className={`findings-chip ${activeFilter === null ? 'active' : ''}`}
            onClick={() => setActiveFilter(null)}
          >
            All ({summary.total})
          </button>
          {TYPE_ORDER.map((type) => {
            const count = summary.by_type[type] ?? 0;
            if (count === 0) return null;
            const info = TYPE_LABELS[type];
            return (
              <button
                key={type}
                className={`findings-chip ${activeFilter === type ? 'active' : ''}`}
                onClick={() => setActiveFilter(activeFilter === type ? null : type)}
              >
                {info?.icon} {info?.label} ({count})
              </button>
            );
          })}
        </div>
        <div className="findings-severity-row">
          <span className="findings-severity-label">
            Severity
            <InfoTip
              text="Critical (CVSS 9.0–10.0), High (7.0–8.9), Medium (4.0–6.9), Low (0.1–3.9). Higher = more urgent."
              label="Severity"
            />
          </span>
          {['critical', 'high', 'medium', 'low', 'info'].map((sev) => {
            const count = summary.by_severity[sev] ?? 0;
            if (count === 0) return null;
            return (
              <span key={sev} className="findings-severity-pill">
                <SeverityBadge label={capitalize(sev)} /> {count}
              </span>
            );
          })}
        </div>
      </div>

      {/* Data sources */}
      {report.data_sources_used.length > 0 && (
        <div className="findings-sources">
          Data sources: {report.data_sources_used.join(', ')}
          <InfoTip text="KEV = CISA Known Exploited Vulnerabilities — CVEs confirmed exploited in the wild" />
        </div>
      )}

      {/* Disclaimer */}
      {report.disclaimer_block && (
        <DisclaimerBanner disclaimerBlock={report.disclaimer_block} variant="full" />
      )}

      {/* Grouped findings */}
      {TYPE_ORDER.map((type) => {
        const items = grouped[type];
        if (!items) return null;
        const info = TYPE_LABELS[type];
        return (
          <section key={type} className="findings-group">
            <h3 className="findings-group-title">
              <span className="findings-group-icon">{info?.icon}</span>
              {info?.label}
              <span className="findings-group-count">{items.length}</span>
            </h3>
            <div className="findings-list">
              {items.map((finding) => {
                const expanded = expandedIds.has(finding.id);
                const isDone = finding.status === 'done';
                return (
                  <div
                    key={finding.id}
                    className={`finding-card finding-card--${finding.severity}${
                      isDone ? ' finding-card--done' : ''
                    }`}
                  >
                    <div className="finding-card-row">
                      <label
                        className="finding-card-check"
                        title={isDone ? 'Mark as open' : 'Mark as remediated'}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={isDone}
                          onChange={(e) => {
                            void setFindingStatus(
                              finding,
                              e.target.checked ? 'done' : 'open',
                            );
                          }}
                          aria-label={`Mark "${finding.title}" as remediated`}
                        />
                      </label>
                      <button
                        className="finding-card-header"
                        onClick={() => toggleExpand(finding.id)}
                        aria-expanded={expanded}
                      >
                        <SeverityBadge label={capitalize(finding.severity)} />
                        {finding.severity_score != null && (
                          <span className="finding-score" title="Severity score (0-100)">
                            {finding.severity_score.toFixed(0)}
                          </span>
                        )}
                        <span className="finding-title">{finding.title}</span>
                        <span className="finding-expand-icon">
                          {expanded ? '\u25b2' : '\u25bc'}
                        </span>
                      </button>
                    </div>
                    {expanded && (
                      <div className="finding-card-body">
                        <p className="finding-description">{finding.description}</p>
                        {finding.affected_assets.length > 0 && (
                          <div className="finding-assets">
                            <span className="finding-assets-label">Affected:</span>
                            {finding.affected_assets.map((a) => (
                              <span key={a} className="finding-asset-chip">{a}</span>
                            ))}
                          </div>
                        )}
                        <div className="finding-meta">
                          <span className="finding-source">Source: {finding.source}</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {/* End list */}
            </div>
          </section>
        );
      })}

      {/* Scan History */}
      <section className="findings-history-section">
        <button
          className="findings-history-toggle"
          onClick={() => setShowHistory((prev) => !prev)}
        >
          {showHistory ? '\u25b2' : '\u25bc'} Scan History
        </button>
        {showHistory && (
          <div className="findings-history-list">
            {history.length === 0 ? (
              <p className="findings-history-empty">No previous scans recorded yet.</p>
            ) : (
              <table className="findings-history-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Tier</th>
                    <th>Critical</th>
                    <th>High</th>
                    <th>Medium</th>
                    <th>Low</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((snap, i) => {
                    const prev = history[i + 1];
                    const delta = (key: 'critical' | 'high' | 'medium' | 'low' | 'total') => {
                      if (!prev) return null;
                      const curr = key === 'total' ? snap.summary.total : (snap.summary.by_severity[key] ?? 0);
                      const before = key === 'total' ? prev.summary.total : (prev.summary.by_severity[key] ?? 0);
                      const diff = curr - before;
                      if (diff === 0) return null;
                      return (
                        <span className={diff > 0 ? 'findings-delta--up' : 'findings-delta--down'}>
                          {diff > 0 ? `▲${diff}` : `▼${Math.abs(diff)}`}
                        </span>
                      );
                    };
                    const d = new Date(snap.generated_at).toLocaleString('en-US', {
                      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
                    });
                    return (
                      <tr key={snap.id}>
                        <td>{d}</td>
                        <td>{capitalize(snap.assessment_tier)}</td>
                        <td>{snap.summary.by_severity.critical ?? 0} {delta('critical')}</td>
                        <td>{snap.summary.by_severity.high ?? 0} {delta('high')}</td>
                        <td>{snap.summary.by_severity.medium ?? 0} {delta('medium')}</td>
                        <td>{snap.summary.by_severity.low ?? 0} {delta('low')}</td>
                        <td>{snap.summary.total} {delta('total')}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

export default FindingsTab;
