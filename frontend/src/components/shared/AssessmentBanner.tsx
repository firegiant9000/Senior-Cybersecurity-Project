import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './AssessmentBanner.css';
import { useAssessmentReadiness } from '../../hooks/useAssessmentReadiness';

const AssessmentBanner: React.FC = () => {
  const { data, loading } = useAssessmentReadiness();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);

  if (loading || dismissed || !data || data.is_ready) return null;

  const missingRequired = data.items.filter(i => i.required && !i.complete);

  return (
    <div className="assessment-banner">
      <div className="assessment-banner-left">
        <div className="assessment-banner-header">
          <span className="assessment-banner-icon">⚠</span>
          <span className="assessment-banner-title">Profile Incomplete</span>
          <span className="assessment-banner-pct">{data.readiness_pct}% complete</span>
        </div>
        <div className="assessment-banner-bar-wrap">
          <div className="assessment-banner-bar" style={{ width: `${data.readiness_pct}%` }} />
        </div>
        {missingRequired.length > 0 && (
          <p className="assessment-banner-missing">
            Missing required: {missingRequired.map(i => i.label).join(', ')}
          </p>
        )}
        <p className="assessment-banner-sub">
          Complete your organization profile to get accurate risk scores and loss projections.
        </p>
      </div>
      <div className="assessment-banner-actions">
        <button className="assessment-banner-cta" onClick={() => navigate('/settings')}>
          Complete Setup
        </button>
        <button className="assessment-banner-dismiss" onClick={() => setDismissed(true)} aria-label="Dismiss profile completeness banner">
          ✕
        </button>
      </div>
    </div>
  );
};

export default AssessmentBanner;
