import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchAISummary,
  fetchAISummaryHistory,
  submitFeedback,
  type AISummaryResponse,
  type FeedbackRequest,
  type HistoryEntry,
} from '../../api/aiSummary';
import { useAuth } from '../../context/AuthContext';
import { useUserContext } from '../../context/UserContext';
import DisclaimerBanner from '../shared/DisclaimerBanner';
import InfoTip from '../shared/InfoTip';
import './AISummaryTab.css';

function riskClass(label: string): string {
  switch (label.toLowerCase()) {
    case 'critical': return 'risk-critical';
    case 'high': return 'risk-high';
    case 'moderate': return 'risk-moderate';
    case 'low': return 'risk-low';
    default: return '';
  }
}

function severityBadgeClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical': return 'ai-risk-badge--critical';
    case 'high':     return 'ai-risk-badge--high';
    case 'medium':
    case 'moderate': return 'ai-risk-badge--moderate';
    default:         return 'ai-risk-badge--low';
  }
}

function severityItemClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical': return 'ai-risk-item--critical';
    case 'high':     return 'ai-risk-item--high';
    case 'medium':
    case 'moderate': return 'ai-risk-item--moderate';
    default:         return 'ai-risk-item--low';
  }
}

const AI_LOADING_STAGES = [
  'Reviewing your findings...',
  'Checking which threats affect your business...',
  'Reviewing software vulnerabilities...',
  'Writing your plain-English summary...',
  'Almost ready...',
];

const AISummaryLoadingBar: React.FC = () => {
  const [stageIndex, setStageIndex] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setStageIndex((i) => (i < AI_LOADING_STAGES.length - 1 ? i + 1 : i));
    }, 3000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="tab-page">
      <div className="ai-summary-loading">
        <p className="ai-summary-loading-title">Generating executive summary</p>
        <div className="ai-summary-progress-track">
          <div className="ai-summary-progress-fill" />
        </div>
        <p className="ai-summary-loading-stage">{AI_LOADING_STAGES[stageIndex]}</p>
        <p className="ai-summary-loading-sub">Synthesizing findings into an actionable narrative.</p>
      </div>
    </div>
  );
};

function parseHistoryOutputText(entry: HistoryEntry): { riskScore: number | null } {
  if (!entry.output_text) return { riskScore: null };
  if (entry.output_format === 'json' || entry.output_text.trimStart().startsWith('{')) {
    try {
      const parsed = JSON.parse(entry.output_text) as Record<string, unknown>;
      const score = typeof parsed.risk_score === 'number' ? parsed.risk_score : null;
      return { riskScore: score };
    } catch {
      return { riskScore: null };
    }
  }
  return { riskScore: null };
}

const AISummaryTab: React.FC = () => {
  const { user } = useAuth();
  const { organization } = useUserContext();
  const userId = user?.uid;
  const [data, setData] = useState<AISummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [minElapsed, setMinElapsed] = useState(false);
  const [error, setError] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackError, setFeedbackError] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);

  const handleFeedback = useCallback(
    async (flag: FeedbackRequest['flag']) => {
      setFeedbackError('');
      try {
        const rating = flag === 'helpful' ? 5 : flag === 'too_vague' ? 2 : 1;
        await submitFeedback({ rating, flag });
        setFeedbackSent(true);
      } catch (err) {
        setFeedbackError(
          err instanceof Error ? err.message : 'Failed to submit feedback',
        );
      }
    },
    [],
  );

  const load = useCallback((forceRefresh = false) => {
    if (!userId) return;
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setMinElapsed(false);
    const minTimer = setTimeout(() => { if (!cancelled) setMinElapsed(true); }, 1500);
    fetchAISummary(controller.signal, forceRefresh)
      .then((result) => { if (!cancelled) setData(result); })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load AI summary');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(minTimer);
    };
  }, [userId]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  useEffect(() => {
    if (!userId) return;
    fetchAISummaryHistory(10, 0)
      .then((resp) => setHistory(resp.items))
      .catch(() => { /* history unavailable — non-fatal */ });
  }, [userId]);

  if (!userId) {
    return <div className="tab-page"><p>Please log in to view the AI summary.</p></div>;
  }

  if (loading || !minElapsed) {
    return <AISummaryLoadingBar />;
  }

  if (error) {
    const lower = error.toLowerCase();
    const isIncomplete =
      lower.includes('incomplete') ||
      lower.includes('enhanced tier') ||
      (lower.includes('profile') && (lower.includes('required') || lower.includes('missing'))) ||
      lower.includes('no vendor') ||
      lower.includes('no domain');
    const isDisabled = lower.includes('disabled') || lower.includes('not enabled');
    return (
      <div className="tab-page">
        <div className="ai-summary-error-card">
          {isIncomplete ? (
            <>
              <span className="ai-summary-error-icon">{'\ud83d\udccb'}</span>
              <p className="ai-summary-error-title">Setup Required</p>
              <p className="ai-summary-error-detail">
                Complete these steps to unlock your AI Executive Summary:
              </p>
              <ul className="ai-summary-setup-checklist">
                <li>Organization name</li>
                <li>Industry &amp; state</li>
                <li>At least one vendor (Technology Stack)</li>
                <li>At least one domain</li>
                <li>At least one security question answered</li>
              </ul>
              <Link to="/org-profile" className="ai-summary-error-action">
                Complete Profile
              </Link>
            </>
          ) : isDisabled ? (
            <>
              <span className="ai-summary-error-icon">{'\ud83d\udd0c'}</span>
              <p className="ai-summary-error-title">AI Summary Unavailable</p>
              <p className="ai-summary-error-detail">
                The AI summary feature is currently disabled by the administrator. Check back later.
              </p>
            </>
          ) : (
            <>
              <span className="ai-summary-error-icon">{'\u26a0'}</span>
              <p className="ai-summary-error-title">Couldn't Generate Summary</p>
              <p className="ai-summary-error-detail">
                The AI service didn't respond. This is usually a temporary hiccup — give it another try in a moment.
              </p>
              <p className="ai-summary-error-detail" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 4 }}>
                Details: {error}
              </p>
              <button className="ai-summary-error-action" onClick={() => load()}>
                Retry
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="tab-page">
        <div className="ai-summary-error-card">
          <span className="ai-summary-error-icon">📋</span>
          <p className="ai-summary-error-title">No Summary Yet</p>
          <p className="ai-summary-error-detail">
            Complete your organization profile and submit an assessment to generate an AI executive summary.
          </p>
          <Link to="/org-profile" className="ai-summary-error-action">
            Complete Profile
          </Link>
        </div>
      </div>
    );
  }

  const generatedDate = new Date(data.generated_at).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
  });

  const hasStructured =
    data.posture_statement != null ||
    data.notable_risks != null ||
    data.data_gaps != null ||
    data.next_steps != null;

  return (
    <div className="tab-page ai-summary-tab">
      {/* Header */}
      <div className="ai-summary-header">
        <div className="ai-summary-title-row">
          <h2 className="ai-summary-title">Executive Summary</h2>
          <div className="ai-summary-badges">
            {data.ai_generated ? (
              <span className="ai-badge ai-badge--ai">AI-Generated</span>
            ) : (
              <span className="ai-badge ai-badge--template">Template-Based</span>
            )}
            <InfoTip text="This summary was written by an AI model based on your findings data. Review before sharing externally." />
            {data.cached && (
              <span className="ai-badge ai-badge--cached">Cached</span>
            )}
          </div>
        </div>
        <div className="ai-summary-header-actions">
          <button
            className="overview-refresh-btn"
            onClick={() => load(true)}
            disabled={loading}
          >
            {loading ? 'Regenerating...' : 'Regenerate'}
          </button>
          <button
            className="ai-summary-print-btn"
            onClick={() => window.print()}
          >
            Print / Save as PDF
          </button>
        </div>
      </div>

      {/* Printable content — everything below is included in print output */}
      <div className="ai-summary-printable">

        {/* Print-only header: hidden on screen, rendered when printing */}
        <div className="ai-summary-print-header">
          <div className="ai-print-org">{organization?.name ?? 'Executive Security Summary'}</div>
          <div className="ai-print-meta">
            <span>Hacker Tracker</span>
            <span>{new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</span>
          </div>
        </div>

      {/* Risk score card + posture statement */}
      <div className="ai-summary-metrics">
        <div className={`ai-summary-risk-card ${riskClass(data.risk_label)}`}>
          <span className="ai-summary-risk-score">{(data.risk_score ?? 0).toFixed(0)}</span>
          <span className="ai-summary-risk-label">{data.risk_label ?? 'Unknown'} Risk</span>
        </div>
        <div className="ai-summary-metric">
          <span className="ai-summary-metric-value">{data.findings_count ?? 0}</span>
          <span className="ai-summary-metric-label">Findings Analyzed</span>
        </div>
        {data.model_used && (
          <div className="ai-summary-metric">
            <span className="ai-summary-metric-value ai-summary-model">{data.model_used}</span>
            <span className="ai-summary-metric-label">Model</span>
          </div>
        )}
      </div>

      {/* Posture statement — prominent single-sentence summary */}
      {data.posture_statement && (
        <div className="ai-posture-banner">
          <p className="ai-posture-statement">{data.posture_statement}</p>
        </div>
      )}

      {/* Narrative */}
      <div className="ai-summary-narrative-card">
        <div className="ai-summary-narrative">
          {(data.narrative ?? '').split('\n').map((paragraph, i) => {
            const trimmed = paragraph.trim();
            if (!trimmed) return null;
            return <p key={i}>{trimmed}</p>;
          })}
        </div>
      </div>

      {/* Notable risks */}
      {data.notable_risks && data.notable_risks.length > 0 && (
        <div className="ai-structured-card">
          <h3 className="ai-structured-card-title">Threats That Need Attention</h3>
          <div className="ai-risk-list">
            {data.notable_risks.map((risk, i) => (
              <div key={i} className={`ai-risk-item ${severityItemClass(risk.severity)}`}>
                <div className="ai-risk-item-header">
                  <span className="ai-risk-item-title">{risk.title}</span>
                  <span className={`ai-risk-badge ${severityBadgeClass(risk.severity)}`}>
                    {risk.severity}
                  </span>
                </div>
                <p className="ai-risk-item-context">{risk.context}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data gaps */}
      {data.data_gaps && data.data_gaps.length > 0 && (
        <div className="ai-structured-card">
          <h3 className="ai-structured-card-title">Missing Information</h3>
          <ul className="ai-gap-list">
            {data.data_gaps.map((gap, i) => (
              <li key={i} className="ai-gap-item">
                <span className="ai-gap-type">{gap.gap_type}</span>
                <span className="ai-gap-impact">{gap.impact}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Next steps / action plan */}
      {data.next_steps && data.next_steps.length > 0 && (
        <div className="ai-structured-card">
          <h3 className="ai-structured-card-title">What to Do Next</h3>
          <ol className="ai-steps-list">
            {data.next_steps
              .slice()
              .sort((a, b) => a.priority - b.priority)
              .map((step, i) => (
                <li key={i} className="ai-step-item">
                  <span className="ai-step-action">{step.action}</span>
                  <span className="ai-step-rationale">{step.rationale}</span>
                </li>
              ))}
          </ol>
        </div>
      )}

      {/* Fallback hint when no structured data */}
      {!hasStructured && data.ai_generated && (
        <p className="ai-summary-prose-hint">
          Structured sections (posture, risks, gaps, actions) will appear here once the AI returns a JSON response.
        </p>
      )}

      {/* Feedback */}
      <div className="ai-summary-feedback">
        {feedbackSent ? (
          <span className="ai-summary-feedback-thanks">Thanks for your feedback!</span>
        ) : (
          <>
            <span className="ai-summary-feedback-label">Was this summary helpful?</span>
            <div className="ai-summary-feedback-buttons">
              <button
                className="ai-feedback-btn ai-feedback-btn--helpful"
                onClick={() => handleFeedback('helpful')}
                title="Helpful"
              >
                {'\ud83d\udc4d'}
              </button>
              <button
                className="ai-feedback-btn ai-feedback-btn--vague"
                onClick={() => handleFeedback('too_vague')}
                title="Too vague"
              >
                {'\ud83e\udd37'}
              </button>
              <button
                className="ai-feedback-btn ai-feedback-btn--inaccurate"
                onClick={() => handleFeedback('inaccurate')}
                title="Inaccurate"
              >
                {'\ud83d\udc4e'}
              </button>
            </div>
            {feedbackError && (
              <span className="ai-summary-feedback-error">{feedbackError}</span>
            )}
          </>
        )}
      </div>

      {/* Past summaries (collapsible) */}
      {history.length > 0 && (
        <div className="ai-history-section">
          <button
            className="ai-history-toggle"
            onClick={() => setHistoryOpen((o) => !o)}
            aria-expanded={historyOpen}
          >
            Past Summaries ({history.length})
            <span className="ai-history-toggle-icon">{historyOpen ? '▲' : '▼'}</span>
          </button>
          {historyOpen && (
            <div className="ai-history-list">
              {history.map((entry) => {
                const { riskScore } = parseHistoryOutputText(entry);
                return (
                  <div key={entry.id} className="ai-history-item">
                    <span className="ai-history-date">
                      {new Date(entry.generated_at).toLocaleString('en-US', {
                        month: 'short', day: 'numeric', year: 'numeric',
                        hour: 'numeric', minute: '2-digit',
                      })}
                    </span>
                    <span className="ai-history-model">{entry.model_name}</span>
                    {riskScore !== null && (
                      <span className="ai-history-score">Risk: {riskScore.toFixed(0)}</span>
                    )}
                    <span className={`ai-history-status ai-history-status--${entry.status}`}>
                      {entry.status}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Meta footer */}
      <div className="ai-summary-footer">
        <span className="ai-summary-generated">Generated {generatedDate}</span>
        {data.disclaimer_block ? (
          <DisclaimerBanner disclaimerBlock={data.disclaimer_block} variant="full" />
        ) : (
          <span className="ai-summary-disclaimer">{data.disclaimer}</span>
        )}
      </div>

      </div>{/* end ai-summary-printable */}
    </div>
  );
};

export default AISummaryTab;
