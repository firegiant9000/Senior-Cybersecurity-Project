import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './AssessmentBanner.css';
import { useAssessmentIntake } from '../../hooks/useAssessmentIntake';

const TIER_GUIDANCE: Record<string, string> = {
  incomplete: 'Complete your basic profile to unlock risk scores and loss projections.',
  basic: 'Add vendors, domains, and security controls to unlock Findings and AI Summary.',
  enhanced: 'Complete remaining fields (revenue, compliance, data types, uploads) for full-confidence analysis.',
};

const AssessmentBanner: React.FC = () => {
  const { data, loading } = useAssessmentIntake();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);

  if (loading || dismissed || !data) return null;
  if (data.current_tier === 'comprehensive') return null;

  const nextTierLabel = data.next_tier
    ? data.tiers.find(t => t.tier === data.next_tier)?.label ?? data.next_tier
    : null;

  return (
    <div className="assessment-banner">
      <div className="assessment-banner-left">
        <div className="assessment-banner-header">
          <span className="assessment-banner-icon">{'\u26A0'}</span>
          <span className="assessment-banner-title">
            {data.current_tier === 'incomplete' ? 'Profile Incomplete' : `Tier: ${data.tiers.find(t => t.tier === data.current_tier)?.label ?? data.current_tier}`}
          </span>
          {nextTierLabel && (
            <span className="assessment-banner-pct">
              {Math.round(data.next_tier_progress)}% toward {nextTierLabel}
            </span>
          )}
        </div>
        {nextTierLabel && (
          <div className="assessment-banner-bar-wrap">
            <div className="assessment-banner-bar" style={{ width: `${data.next_tier_progress}%` }} />
          </div>
        )}
        {data.fields_to_advance.length > 0 && (
          <p className="assessment-banner-missing">
            {data.fields_to_advance.length} field{data.fields_to_advance.length > 1 ? 's' : ''} needed to advance
          </p>
        )}
        <p className="assessment-banner-sub">
          {TIER_GUIDANCE[data.current_tier] ?? 'Complete your profile for better analysis.'}
        </p>
      </div>
      <div className="assessment-banner-actions">
        <button className="assessment-banner-cta" onClick={() => navigate('/org-profile')}>
          Complete Setup
        </button>
        <button className="assessment-banner-dismiss" onClick={() => setDismissed(true)} aria-label="Dismiss profile completeness banner">
          {'\u2715'}
        </button>
      </div>
    </div>
  );
};

export default AssessmentBanner;
