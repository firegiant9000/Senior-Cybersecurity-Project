import React, { useState } from 'react';
import type { LossProjection } from '../../api/lossProjection';
import ConfidenceBadge, { getConfidenceExplanation } from '../shared/ConfidenceBadge';
import './ProjectedLossCard.css';

interface Props {
    data: LossProjection | null;
    loading: boolean;
}

const ProjectedLossCard: React.FC<Props> = ({ data, loading }) => {
    const [showMethodology, setShowMethodology] = useState(false);

    const value = loading || !data?.has_data ? '—' : data.projected_annual_loss_formatted;
    const tier = data?.confidence_level ?? 'Low';
    const tierExplanation = getConfidenceExplanation(tier, 'projection');

    return (
        <div className="card projected-loss-card">
            <span className="projected-loss-title">Projected Annual Loss</span>
            <span className="projected-loss-value">{value}</span>
            {data?.has_data && (
                <span className="projected-loss-context">
                    {data.sector || 'national average'}
                    {data.state ? ` · ${data.state}` : ''}
                </span>
            )}
            {data?.has_data && (
                <div className="projected-loss-meta">
                    <ConfidenceBadge tier={tier} context="projection" />
                    <button
                        type="button"
                        className="projected-loss-methodology-toggle"
                        onClick={() => setShowMethodology((v) => !v)}
                        aria-expanded={showMethodology}
                    >
                        {showMethodology ? '▲' : '▼'} How this is calculated
                    </button>
                </div>
            )}
            {showMethodology && data?.has_data && (
                <div className="projected-loss-methodology">
                    <p className="projected-loss-methodology-line">{tierExplanation}</p>
                    <p className="projected-loss-methodology-line">{data.methodology}</p>
                    <ul className="projected-loss-methodology-list">
                        {data.ic3_data_years && (
                            <li><strong>Years included:</strong> {data.ic3_data_years}</li>
                        )}
                        {data.ic3_incident_count != null && (
                            <li><strong>IC3 incidents in sample:</strong> {data.ic3_incident_count.toLocaleString()}</li>
                        )}
                        {data.ic3_avg_loss_per_incident != null && (
                            <li>
                                <strong>Avg loss per incident (sample):</strong>{' '}
                                ${data.ic3_avg_loss_per_incident.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </li>
                        )}
                        <li>
                            <strong>Size multiplier ({data.employee_range}):</strong> ×{data.size_multiplier}
                        </li>
                    </ul>
                </div>
            )}
        </div>
    );
};

export default ProjectedLossCard;
