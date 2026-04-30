import React from 'react';
import './ConfidenceBadge.css';

export type ConfidenceTier = 'High' | 'Medium' | 'Low';

export type ConfidenceContext = 'projection' | 'executive' | 'smb';

interface Props {
    tier: ConfidenceTier;
    context?: ConfidenceContext;
    explanation?: string;
}

const DEFAULT_EXPLANATIONS: Record<ConfidenceContext, Record<ConfidenceTier, string>> = {
    projection: {
        High: 'Based on IC3 reports for your sector and your state.',
        Medium: 'Based on IC3 reports for your sector; state-level data was not available, so the national average for your sector is used.',
        Low: 'Based on the national IC3 average across all sectors; sector-specific data was not available.',
    },
    executive: {
        High: 'All three source datasets (KEV, IC3, NVD) returned data.',
        Medium: 'Two of the three source datasets returned data.',
        Low: 'Only one of the three source datasets returned data.',
    },
    smb: {
        High: 'Multiple IC3 reports available for your industry.',
        Medium: 'Limited IC3 reports available for your industry.',
        Low: 'Very few IC3 reports available for your industry; figures may be less stable due to the small sample size.',
    },
};

export function getConfidenceExplanation(
    tier: ConfidenceTier,
    context: ConfidenceContext,
): string {
    return DEFAULT_EXPLANATIONS[context][tier];
}

const ConfidenceBadge: React.FC<Props> = ({ tier, context = 'projection', explanation }) => {
    const text = explanation ?? DEFAULT_EXPLANATIONS[context][tier];
    return (
        <span className="confidence-badge" title={text}>
            <span className={`confidence-dot ${tier}`} aria-hidden="true" />
            <span className="confidence-label">{tier} Confidence</span>
        </span>
    );
};

export default ConfidenceBadge;
