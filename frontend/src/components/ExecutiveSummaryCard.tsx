import React, { useState } from 'react';
import './ExecutiveSummaryCard.css';
import type { ExecutiveSummary } from '../api/executiveSummary';
import { fmtLoss } from '../utils/fmtLoss';

interface Props {
    data: ExecutiveSummary | null;
    loading: boolean;
    error?: string;
}

const ExecutiveSummaryCard: React.FC<Props> = ({ data, loading, error }) => {
    const [showMethodology, setShowMethodology] = useState(false);

    if (loading) {
        return <div className="exec-summary-skeleton" aria-label="Loading executive summary" />;
    }

    if (error) {
        return (
            <div className="exec-summary-card" role="region" aria-label="Executive Summary">
                <div className="exec-summary-body">
                    <p className="exec-disclaimer">Failed to load executive summary: {error}</p>
                </div>
            </div>
        );
    }

    if (!data) {
        return null;
    }

    const generatedDate = new Date(data.generated_at).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
    });

    return (
        <div className="exec-summary-card" role="region" aria-label="Executive Summary">
            {/* ── Header ── */}
            <div className="exec-summary-header">
                <div className="exec-summary-title-group">
                    <span className="exec-summary-title">Executive Summary</span>
                    <span className="exec-summary-subtitle">
                        SMB Cyber Threat Landscape · {data.data_year_range}
                    </span>
                </div>
                <div className="exec-summary-risk-badge">
                    <span className="exec-risk-score">{data.risk_score.toFixed(0)}</span>
                    <span className={`exec-risk-label-pill ${data.risk_label}`}>
                        {data.risk_label} Risk
                    </span>
                </div>
            </div>

            {/* ── Body ── */}
            <div className="exec-summary-body">
                {/* Key metrics */}
                <div className="exec-metrics-row">
                    <div className="exec-metric">
                        <div className="exec-metric-label">Est. Total Losses</div>
                        <div className="exec-metric-value">{data.loss_estimate_formatted}</div>
                    </div>
                    <div className="exec-metric">
                        <div className="exec-metric-label">Actively Exploited CVEs</div>
                        <div className="exec-metric-value">{data.kev_count.toLocaleString()}</div>
                    </div>
                    <div className="exec-metric">
                        <div className="exec-metric-label">Critical CVEs</div>
                        <div className="exec-metric-value">{data.critical_cve_count.toLocaleString()}</div>
                    </div>
                </div>

                {/* Top threats */}
                {data.top_threats.length > 0 && (
                    <div className="exec-threats-section">
                        <div className="exec-threats-label">Top Threats by Financial Impact</div>
                        <div className="exec-threats-list">
                            {data.top_threats.map((t, i) => (
                                <div key={t.name} className="exec-threat-chip">
                                    <span className="exec-threat-rank">#{i + 1}</span>
                                    <span className="exec-threat-name">{t.name}</span>
                                    <span className="exec-threat-loss">{fmtLoss(t.total_loss)}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Confidence + metadata */}
                <div className="exec-meta-row">
                    <span className="exec-confidence-badge">
                        <span className={`exec-confidence-dot ${data.confidence_level}`} />
                        {data.confidence_level} Confidence
                    </span>
                    <span>Generated {generatedDate}</span>
                    <button
                        className="exec-methodology-toggle"
                        onClick={() => setShowMethodology(v => !v)}
                        aria-expanded={showMethodology}
                    >
                        {showMethodology ? '▲' : '▼'} Methodology
                    </button>
                </div>

                {showMethodology && (
                    <div className="exec-methodology-text">{data.methodology}</div>
                )}

                {/* Disclaimer */}
                <p className="exec-disclaimer">{data.disclaimer}</p>
            </div>
        </div>
    );
};

export default ExecutiveSummaryCard;
