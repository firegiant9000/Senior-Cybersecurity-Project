import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchFindings,
  fetchFindingsHistory,
  type FindingsReport,
  type Finding,
  type SnapshotListItem,
} from '../../api/findings';
import { useAuth } from '../../context/AuthContext';
import SeverityBadge from '../shared/SeverityBadge';
import DisclaimerBanner from '../shared/DisclaimerBanner';
import './FindingsTab.css';

const TYPE_LABELS: Record<string, { label: string; icon: string }> = {
  threat_exposure: { label: 'Threat Exposure', icon: '\u26a0' },
  vendor_exposure: { label: 'Vendor Exposure', icon: '\ud83d\udee1' },
  data_gap: { label: 'Data Gaps', icon: '\ud83d\udcca' },
  recommended_action: { label: 'Recommended Actions', icon: '\u2705' },
};

const TYPE_ORDER = ['threat_exposure', 'vendor_exposure', 'data_gap', 'recommended_action'];

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const LOADING_STAGES = [
  'Resolving DNS records...',
  'Running SSL analysis...',
  'Matching CVE database...',
  'Scoring vendor exposure...',
  'Generating findings report...',
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
    const isIncomplete = error.includes('incomplete');
    return (
      <div className="tab-page">
        <div className="findings-error-card">
          {isIncomplete ? (
            <>
              <span className="findings-error-icon">{'\ud83d\udccb'}</span>
              <p className="findings-error-title">Profile Incomplete</p>
              <p className="findings-error-detail">
                Complete all required fields in your organization profile before viewing findings.
              </p>
              <Link to="/org-profile" className="findings-error-action">
                Complete Profile
              </Link>
            </>
          ) : (
            <>
              <span className="findings-error-icon">{'\u26a0'}</span>
              <p className="findings-error-title">Failed to Load Findings</p>
              <p className="findings-error-detail">{error}</p>
              <button className="findings-error-action" onClick={load}>
                Retry
              </button>
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
        <button
          className="overview-refresh-btn"
          onClick={load}
          disabled={loading}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
        <span className="findings-meta">
          {summary.total} finding{summary.total !== 1 ? 's' : ''} &middot; Generated {generatedDate}
        </span>
      </div>

      {/* Summary chips */}
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

      {/* Severity pills */}
      <div className="findings-severity-row">
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

      {/* Data sources */}
      {report.data_sources_used.length > 0 && (
        <div className="findings-sources">
          Data sources: {report.data_sources_used.join(', ')}
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
                return (
                  <div
                    key={finding.id}
                    className={`finding-card finding-card--${finding.severity}`}
                  >
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
