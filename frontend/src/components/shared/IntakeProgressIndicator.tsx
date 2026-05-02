import { useEffect, useMemo, useRef, useState } from "react";
import type {
  AssessmentIntakeResponse,
  AssessmentTier,
} from "../../api/assessmentIntake";
import "./IntakeProgressIndicator.css";

interface Props {
  preview: AssessmentIntakeResponse | null;
  loading: boolean;
}

const TIER_LABEL: Record<AssessmentTier, string> = {
  incomplete: "Incomplete",
  basic: "Basic",
  enhanced: "Enhanced",
  comprehensive: "Comprehensive",
};

const TIER_RANK: Record<AssessmentTier, number> = {
  incomplete: 0,
  basic: 1,
  enhanced: 2,
  comprehensive: 3,
};

const IntakeProgressIndicator: React.FC<Props> = ({ preview, loading }) => {
  // Track tier transitions and unlocked-feature deltas across renders so we can
  // surface a brief "just unlocked" toast whenever new things become available.
  const lastTierRef = useRef<AssessmentTier | null>(null);
  const lastUnlocksRef = useRef<Set<string>>(new Set());
  const [toast, setToast] = useState<string | null>(null);

  // Cumulative completion across every tier requirement. This is the
  // "overall onboarding progress" — it climbs steadily as fields fill, rather
  // than resetting at each tier boundary.
  const overall = useMemo(() => {
    if (!preview) return { metCount: 0, totalCount: 0, percent: 0 };
    let met = 0;
    let total = 0;
    for (const td of preview.tiers) {
      total += td.requirements.length;
      met += td.requirements.filter((r) => r.met).length;
    }
    return {
      metCount: met,
      totalCount: total,
      percent: total > 0 ? (met / total) * 100 : 0,
    };
  }, [preview]);

  useEffect(() => {
    if (!preview) return;

    const currentUnlocks = new Set<string>();
    for (const td of preview.tiers) {
      if (td.all_met) {
        for (const u of td.unlocks) currentUnlocks.add(u);
      }
    }

    const prevUnlocks = lastUnlocksRef.current;
    const newlyUnlocked = [...currentUnlocks].filter((u) => !prevUnlocks.has(u));
    const tierChanged =
      lastTierRef.current !== null &&
      lastTierRef.current !== preview.current_tier &&
      TIER_RANK[preview.current_tier] > TIER_RANK[lastTierRef.current];

    if (newlyUnlocked.length > 0 || tierChanged) {
      const msg = tierChanged
        ? `You reached ${TIER_LABEL[preview.current_tier]}! New: ${
            newlyUnlocked.slice(0, 2).join(", ") || "more features"
          }`
        : `Unlocked: ${newlyUnlocked.slice(0, 2).join(", ")}${
            newlyUnlocked.length > 2 ? ` +${newlyUnlocked.length - 2}` : ""
          }`;
      setToast(msg);
      const t = setTimeout(() => setToast(null), 4000);
      lastUnlocksRef.current = currentUnlocks;
      lastTierRef.current = preview.current_tier;
      return () => clearTimeout(t);
    }

    lastUnlocksRef.current = currentUnlocks;
    lastTierRef.current = preview.current_tier;
  }, [preview]);

  if (!preview) {
    return (
      <div
        className="intake-progress-indicator intake-progress-indicator--placeholder"
        aria-live="polite"
      >
        <span className="intake-progress-indicator-placeholder-text">
          Fill in fields below to see your overall assessment progress.
        </span>
      </div>
    );
  }

  const currentLabel = TIER_LABEL[preview.current_tier];
  const nextLabel = preview.next_tier ? TIER_LABEL[preview.next_tier] : null;
  const nextTierRemaining =
    preview.tiers
      .find((t) => t.tier === preview.next_tier)
      ?.requirements.filter((r) => !r.met).length ?? 0;

  return (
    <div
      className={`intake-progress-indicator${loading ? " is-loading" : ""}`}
      aria-live="polite"
    >
      <div className="intake-progress-indicator-row">
        <div className="intake-progress-indicator-label-block">
          <span className="intake-progress-indicator-eyebrow">
            Overall Assessment Progress
          </span>
          <span className="intake-progress-indicator-tier">
            Current tier: {currentLabel}
          </span>
        </div>

        <div className="intake-progress-indicator-bar-block">
          <div className="intake-progress-indicator-bar">
            <div
              className="intake-progress-indicator-fill"
              style={{ width: `${Math.min(overall.percent, 100)}%` }}
            />
          </div>
          <div className="intake-progress-indicator-bar-meta">
            <span className="intake-progress-indicator-count">
              {overall.metCount} of {overall.totalCount} items
            </span>
            <span className="intake-progress-indicator-pct">
              {Math.round(overall.percent)}%
            </span>
          </div>
        </div>

        <div className="intake-progress-indicator-next-block">
          {nextLabel ? (
            <>
              <span className="intake-progress-indicator-next-eyebrow">
                Next milestone
              </span>
              <span className="intake-progress-indicator-next-text">
                {nextTierRemaining} more to unlock {nextLabel}
              </span>
            </>
          ) : (
            <span className="intake-progress-indicator-maxed">
              ✓ All milestones unlocked
            </span>
          )}
        </div>
      </div>

      {toast && (
        <div className="intake-progress-indicator-toast" role="status">
          ✓ {toast}
        </div>
      )}
    </div>
  );
};

export default IntakeProgressIndicator;
