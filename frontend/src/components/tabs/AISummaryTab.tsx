import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchAISummary,
  submitFeedback,
  type AISummaryResponse,
  type FeedbackRequest,
} from '../../api/aiSummary';
import { useAuth } from '../../context/AuthContext';
import DisclaimerBanner from '../shared/DisclaimerBanner';
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

const AISummaryTab: React.FC = () => {
  const { user } = useAuth();
  const [data, setData] = useState<AISummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackError, setFeedbackError] = useState('');

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

  const load = useCallback(() => {
    if (!user) return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetchAISummary(controller.signal)
      .then(setData)
      .catch((err) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Failed to load AI summary');
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  if (!user) {
    return <div className="tab-page"><p>Please log in to view the AI summary.</p></div>;
  }

  if (loading && !data) {
    return (
      <div className="tab-page">
        <div className="ai-summary-loading">
          <div className="ai-summary-loading-spinner" />
          <p>Generating executive summary...</p>
          <p className="ai-summary-loading-sub">
            Synthesizing findings into an actionable narrative.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    const isIncomplete = error.includes('incomplete');
    const isDisabled = error.includes('disabled');
    return (
      <div className="tab-page">
        <div className="ai-summary-error-card">
          {isIncomplete ? (
            <>
              <span className="ai-summary-error-icon">{'\ud83d\udccb'}</span>
              <p className="ai-summary-error-title">Profile Incomplete</p>
              <p className="ai-summary-error-detail">
                Complete all required fields in your organization profile before generating a summary.
              </p>
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
              <p className="ai-summary-error-title">Failed to Generate Summary</p>
              <p className="ai-summary-error-detail">{error}</p>
              <button className="ai-summary-error-action" onClick={load}>
                Retry
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  if (!data) return null;

  const generatedDate = new Date(data.generated_at).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
  });

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
            {data.cached && (
              <span className="ai-badge ai-badge--cached">Cached</span>
            )}
          </div>
        </div>
        <button
          className="overview-refresh-btn"
          onClick={load}
          disabled={loading}
        >
          {loading ? 'Regenerating...' : 'Regenerate'}
        </button>
      </div>

      {/* Risk score card */}
      <div className="ai-summary-metrics">
        <div className={`ai-summary-risk-card ${riskClass(data.risk_label)}`}>
          <span className="ai-summary-risk-score">{data.risk_score.toFixed(0)}</span>
          <span className="ai-summary-risk-label">{data.risk_label} Risk</span>
        </div>
        <div className="ai-summary-metric">
          <span className="ai-summary-metric-value">{data.findings_count}</span>
          <span className="ai-summary-metric-label">Findings Analyzed</span>
        </div>
        {data.model_used && (
          <div className="ai-summary-metric">
            <span className="ai-summary-metric-value ai-summary-model">{data.model_used}</span>
            <span className="ai-summary-metric-label">Model</span>
          </div>
        )}
      </div>

      {/* Narrative */}
      <div className="ai-summary-narrative-card">
        <div className="ai-summary-narrative">
          {data.narrative.split('\n').map((paragraph, i) => {
            const trimmed = paragraph.trim();
            if (!trimmed) return null;
            return <p key={i}>{trimmed}</p>;
          })}
        </div>
      </div>

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

      {/* Meta footer */}
      <div className="ai-summary-footer">
        <span className="ai-summary-generated">Generated {generatedDate}</span>
        {data.disclaimer_block ? (
          <DisclaimerBanner disclaimerBlock={data.disclaimer_block} variant="full" />
        ) : (
          <span className="ai-summary-disclaimer">{data.disclaimer}</span>
        )}
      </div>
    </div>
  );
};

export default AISummaryTab;
