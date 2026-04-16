import { useNavigate, useLocation } from 'react-router-dom';
import { useAssessmentIntake } from '../../hooks/useAssessmentIntake';
import type { AssessmentTier, TierDefinition } from '../../api/assessmentIntake';
import './TierProgress.css';

const TIER_ORDER: AssessmentTier[] = ['basic', 'enhanced', 'comprehensive'];

const TIER_ICONS: Record<AssessmentTier, string> = {
  incomplete: '\u25CB',
  basic: '\u25D2',
  enhanced: '\u25D4',
  comprehensive: '\u25CF',
};

const SETTINGS_SECTION_ID: Record<string, string> = {
  vendors: 'section-vendors',
  domains: 'section-domains',
  uploads: 'section-uploads',
  security_controls: 'section-security-profile',
  security_controls_depth: 'section-security-profile',
  compliance_frameworks: 'section-security-profile',
  data_types: 'section-security-profile',
};

function getTierStatus(
  tier: AssessmentTier,
  currentTier: AssessmentTier,
): 'completed' | 'current' | 'locked' {
  if (currentTier === 'incomplete') return 'locked';
  const currentIdx = TIER_ORDER.indexOf(currentTier);
  const tierIdx = TIER_ORDER.indexOf(tier);
  if (tierIdx < currentIdx) return 'completed';
  if (tierIdx === currentIdx) return 'current';
  return 'locked';
}

export default function TierProgress() {
  const { data, loading } = useAssessmentIntake();
  const navigate = useNavigate();
  const location = useLocation();

  if (loading) {
    return <div className="tier-progress tier-progress--loading">Loading tier status...</div>;
  }
  if (!data) return null;

  const handleFix = (key: string) => {
    const sectionId = SETTINGS_SECTION_ID[key];
    if (location.pathname === '/org-profile' && sectionId) {
      document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      navigate('/org-profile', { state: { scrollTo: sectionId } });
    }
  };

  return (
    <div className="tier-progress">
      <div className="tier-progress__header">
        <h3>Assessment Tiers</h3>
        {data.next_tier && (
          <span className="tier-progress__next-hint">
            {Math.round(data.next_tier_progress)}% toward {data.next_tier}
          </span>
        )}
      </div>

      <div className="tier-progress__ladder">
        {data.tiers.map((td: TierDefinition) => {
          const status = getTierStatus(td.tier, data.current_tier);
          return (
            <div
              key={td.tier}
              className={`tier-card tier-card--${status}`}
            >
              <div className="tier-card__header">
                <span className="tier-card__icon">{TIER_ICONS[td.tier]}</span>
                <span className="tier-card__label">{td.label}</span>
                {status === 'completed' && <span className="tier-card__badge tier-card__badge--done">{'\u2713'} Complete</span>}
                {status === 'current' && <span className="tier-card__badge tier-card__badge--active">Current</span>}
                {status === 'locked' && <span className="tier-card__badge tier-card__badge--locked">Locked</span>}
              </div>

              <p className="tier-card__desc">{td.description}</p>

              {/* Requirements */}
              <div className="tier-card__reqs">
                {td.requirements.map((req) => (
                  <div key={req.key} className={`tier-req ${req.met ? 'tier-req--met' : 'tier-req--unmet'}`}>
                    <span className="tier-req__check">{req.met ? '\u2713' : '\u2012'}</span>
                    <span className="tier-req__label">{req.label}</span>
                    <span className="tier-req__detail">{req.detail}</span>
                    {!req.met && SETTINGS_SECTION_ID[req.key] && (
                      <button
                        className="tier-req__fix"
                        onClick={() => handleFix(req.key)}
                      >
                        Fix
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Unlocks */}
              <div className="tier-card__unlocks">
                <span className="tier-card__unlocks-label">
                  {status === 'locked' ? 'Unlocks:' : 'Includes:'}
                </span>
                {td.unlocks.map((u) => (
                  <span key={u} className="tier-card__unlock-chip">{u}</span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {data.fields_to_advance.length > 0 && data.next_tier && (
        <div className="tier-progress__advance">
          <strong>To reach {data.next_tier}:</strong>{' '}
          complete {data.fields_to_advance.join(', ')}.
        </div>
      )}
    </div>
  );
}
