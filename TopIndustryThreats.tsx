import React from "react";
import type { AttackTypeStats } from "../api/dashboardSummary";
import WidgetSkeleton from "./WidgetSkeleton";

interface Props {
  industryLabel: string;
  data: AttackTypeStats[];
  loading: boolean;
}

const TopIndustryThreats: React.FC<Props> = ({ industryLabel, data, loading }) => {
  if (loading) {
    return (
      <div className="card top-threats-panel top-threats-panel--loading">
        <WidgetSkeleton variant="chart" />
      </div>
    );
  }
  const sorted = [...data].sort((a, b) => b.complaint_count - a.complaint_count).slice(0, 8);

  if (sorted.length === 0) {
    return (
      <div className="card top-threats-panel">
        <h3 className="top-threats-heading">Top Threats in {industryLabel}</h3>
        <p className="top-threats-empty">No sector-matched complaint data yet.</p>
      </div>
    );
  }

  return (
    <div className="card top-threats-panel">
      <h3 className="top-threats-heading">Top Threats in {industryLabel}</h3>
      <ol className="top-threats-list">
        {sorted.map((row, i) => (
          <li key={row.attack_type} className="top-threats-item">
            <span className="top-threats-rank">{i + 1}</span>
            <span className="top-threats-name">{row.attack_type}</span>
            <span className="top-threats-count">
              {row.complaint_count.toLocaleString()}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
};

export default TopIndustryThreats;
