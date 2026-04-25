import type { TierDefinition } from "../../api/assessmentIntake";

export interface ProgressSummaryProps {
  currentTier: string;
  nextTier: string | null;
  nextTierProgress: number;
  fieldsToAdvance: string[];
  tierDefinitions: TierDefinition[];
}

export default function ProgressSummary({
  currentTier,
  nextTier,
  nextTierProgress,
  fieldsToAdvance,
  tierDefinitions,
}: ProgressSummaryProps) {
  const currentTierDef = tierDefinitions.find((t) => t.tier === currentTier);

  return (
    <div className="intake-progress-summary">
      <div className="intake-tier-status">
        <div className="intake-tier-current">
          <h4>Current Tier</h4>
          <p className="intake-tier-name">{currentTierDef?.label || "Incomplete"}</p>
          <p className="intake-tier-description">{currentTierDef?.description}</p>
        </div>

        {nextTier && (
          <div className="intake-tier-next">
            <h4>Next Tier: {nextTier}</h4>
            <div className="intake-progress-bar-container">
              <div className="intake-progress-bar">
                <div
                  className="intake-progress-fill"
                  style={{ width: `${Math.min(nextTierProgress, 100)}%` }}
                />
              </div>
              <p className="intake-progress-text">
                {Math.round(nextTierProgress)}% Complete
              </p>
            </div>

            {fieldsToAdvance.length > 0 && (
              <div className="intake-fields-remaining">
                <p className="intake-fields-label">
                  Still needed to unlock {nextTier}:
                </p>
                <ul className="intake-fields-list">
                  {fieldsToAdvance.map((field) => (
                    <li key={field}>✓ {field}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {currentTierDef?.unlocks && currentTierDef.unlocks.length > 0 && (
        <div className="intake-unlocks">
          <h4>Unlocked Features</h4>
          <ul className="intake-unlocks-list">
            {currentTierDef.unlocks.map((feature) => (
              <li key={feature}>★ {feature}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
