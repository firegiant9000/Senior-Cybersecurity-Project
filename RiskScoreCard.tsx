import React from "react";
import type { PersonalRiskScoreResult } from "../utils/personalizedDashboard";
import { riskScoreColor } from "../utils/personalizedDashboard";
import WidgetSkeleton from "./WidgetSkeleton";

interface Props {
  result: PersonalRiskScoreResult | null;
  loading: boolean;
  emptyMessage?: string;
}

const RiskScoreCard: React.FC<Props> = ({
  result,
  loading,
  emptyMessage = "Complete organization setup to see your risk score.",
}) => {
  if (loading) return <WidgetSkeleton variant="chart" />;
  if (!result) {
    return (
      <div className="card risk-score-card risk-score-card--empty">
        <span className="overview-stat-title risk-score-title">Your Risk Score</span>
        <p className="risk-score-empty-msg">{emptyMessage}</p>
      </div>
    );
  }

  const { score, factors } = result;
  const color = riskScoreColor(score);

  return (
    <div className="card risk-score-card">
      <span
        className="overview-stat-title risk-score-title"
        style={{ color }}
      >
        Your Risk Score
      </span>
      <div className="risk-score-gauge-wrap">
        <svg className="risk-score-gauge" viewBox="0 0 120 72" aria-hidden>
          <path
            d="M 12 60 A 48 48 0 0 1 108 60"
            pathLength={100}
            fill="none"
            stroke="var(--border)"
            strokeWidth="10"
            strokeLinecap="round"
          />
          <path
            d="M 12 60 A 48 48 0 0 1 108 60"
            pathLength={100}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={`${score} ${100 - score}`}
          />
        </svg>
        <div className="risk-score-number" style={{ color }}>
          {score}
        </div>
      </div>
      <span className="risk-score-legend">
        Green &lt;30 · Yellow 30–60 · Red &gt;60
      </span>
      <ul className="risk-score-factors">
        {factors.map((f) => (
          <li key={f.label}>
            <span className="risk-score-factor-label">{f.label}</span>
            <span className="risk-score-factor-detail">{f.detail}</span>
            <span className="risk-score-factor-pts">~{f.contribution} pts</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default RiskScoreCard;
