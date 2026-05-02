import React, { useState } from 'react';
import './ExecutiveSummaryCard.css';
import type { ExecutiveSummary } from '../../api/executiveSummary';
import { fmtLoss } from '../../utils/fmtLoss';
import DisclaimerBanner from '../shared/DisclaimerBanner';
import ConfidenceBadge from '../shared/ConfidenceBadge';

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

    if (!data.has_data) {
        return (
            <div className="exec-summary-card" role="region" aria-label="Executive Summary">
                <div className="exec-summary-body">
                    <p className="exec-disclaimer">
                        No threat intelligence data has been ingested yet. Run the data pipeline to populate the executive summary.
                    </p>
                </div>
            </div>
        );
    }

    const generatedDate = new Date(data.generated_at).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
    });

    return (
        <div className="exec-summary-card" role="region" aria-label="Executive Summary">
            {/* ── Header ── */}
            <div className="exec-summary-header">
                <div className="exec-summary-title-group">
                    <span className="exec-summary-title">Cyber Risk Snapshot for Your Industry</span>
                    <span className="exec-summary-subtitle">
                        Small-Business Threat Landscape · {data.data_year_range}
                    </span>
                </div>
            </div>

            {/* ── Body ── */}
            <div className="exec-summary-body">
                {/* Key metrics */}
                <div className="exec-metrics-row">
                    <div className="exec-metric">
                        <div className="exec-metric-label">
                            Reported Cyber Losses · {data.data_year_range}
                        </div>
                        <div className="exec-metric-value">{data.loss_estimate_formatted}</div>
                        <div className="exec-metric-sublabel">FBI IC3 historical sum (all sectors)</div>
                    </div>
                    <div className="exec-metric">
                        <div className="exec-metric-label">Vulnerabilities Being Actively Attacked</div>
                        <div className="exec-metric-value">{data.kev_count.toLocaleString()}</div>
                    </div>
                    <div className="exec-metric">
                        <div className="exec-metric-label">Severe Vulnerabilities in the Wild</div>
                        <div className="exec-metric-value">{data.critical_cve_count.toLocaleString()}</div>
                    </div>
                </div>

                {/* Top threats */}
                {data.top_threats.length > 0 && (
                    <div className="exec-threats-section">
                        <div className="exec-threats-label">Most Costly Attack Types</div>
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
                    <ConfidenceBadge tier={data.confidence_level} context="executive" />
                    <span>Generated {generatedDate}</span>
                    <button
                        className="exec-methodology-toggle"
                        onClick={() => setShowMethodology(v => !v)}
                        aria-expanded={showMethodology}
                    >
                        {showMethodology ? '▲' : '▼'} How we score this
                    </button>
                    <button
                        type="button"
                        className="exec-export-btn"
                        onClick={() => window.open('/report/executive?autoprint=1', '_blank')}
                        aria-label="Open printable executive report in a new tab"
                    >
                        ⤓ Export Report
                    </button>
                </div>

                {showMethodology && (
                    <div className="exec-methodology-text">{data.methodology}</div>
                )}

                {/* Disclaimer */}
                {data.disclaimer_block ? (
                    <DisclaimerBanner disclaimerBlock={data.disclaimer_block} variant="compact" />
                ) : (
                    <p className="exec-disclaimer">{data.disclaimer}</p>
                )}
            </div>
        </div>
    );
};

export default ExecutiveSummaryCard;
