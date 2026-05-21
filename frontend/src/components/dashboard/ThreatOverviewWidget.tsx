import React, { useEffect, useState } from "react";
import "./ThreatOverviewWidget.css";
import type { DashboardData } from "../../hooks/useDashboardData";
import { fetchIngestFreshness } from "../../api/ingest";
import { formatDateWithTz } from "../../utils/formatTime";

interface Props {
  data: DashboardData;
  loading: boolean;
}

const GLOSSARY = [
  {
    abbr: "CVSS",
    def: "Common Vulnerability Scoring System — 0–10 severity score for each CVE. Higher means easier to exploit and more damaging.",
  },
  {
    abbr: "KEV",
    def: "CISA's Known Exploited Vulnerabilities catalog. If a CVE is on this list, attackers are actively using it in the wild — patch first.",
  },
  {
    abbr: "EPSS",
    def: "Exploit Prediction Scoring System — 0–1 probability the CVE will be exploited in the next 30 days. Sharpens CVSS-only triage.",
  },
];

function pickRelevantIngestTimestamp(
  sources: Array<{ source: string; last_successful_run_at: string | null }>,
): string | null {
  // Prefer NVD / KEV freshness since those drive the CVE counts shown here.
  const candidates = sources
    .filter((s) => /nvd|kev|cve/i.test(s.source))
    .map((s) => s.last_successful_run_at)
    .filter((d): d is string => Boolean(d));
  if (candidates.length > 0) {
    return candidates.reduce((a, b) => (a > b ? a : b));
  }
  const any = sources.map((s) => s.last_successful_run_at).filter((d): d is string => Boolean(d));
  return any.length > 0 ? any.reduce((a, b) => (a > b ? a : b)) : null;
}

const ThreatOverviewWidget: React.FC<Props> = ({ data, loading }) => {
  const [lastIngestAt, setLastIngestAt] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchIngestFreshness(controller.signal)
      .then((r) => setLastIngestAt(pickRelevantIngestTimestamp(r.sources)))
      .catch(() => {
        /* non-fatal — banner just hides the timestamp */
      });
    return () => controller.abort();
  }, []);

  const totalCves = data.severityDistribution.reduce((s, d) => s + d.count, 0);
  const highSeverity = data.severityDistribution
    .filter((d) => d.severity === "Critical" || d.severity === "High")
    .reduce((s, d) => s + d.count, 0);
  const topVendors = (data.riskScoreStats?.top_vendors ?? []).slice(0, 5);

  const fmt = (n: number) => (loading ? "—" : n.toLocaleString());

  return (
    <section className="threat-overview-widget" aria-label="Threat intelligence overview">
      <div className="threat-overview-header">
        <span className="threat-overview-header__title">Threat Intelligence Overview</span>
        <span className="threat-overview-header__ingest">
          {lastIngestAt
            ? `Last CVE ingest: ${formatDateWithTz(lastIngestAt)}`
            : "Last CVE ingest: —"}
        </span>
      </div>

      <div className="threat-overview-stat">
        <span className="threat-overview-stat__label">CVEs Ingested</span>
        <span className="threat-overview-stat__value">{fmt(totalCves)}</span>
        <span className="threat-overview-stat__sub">in NVD database</span>
      </div>
      <div className="threat-overview-stat">
        <span className="threat-overview-stat__label">KEV Count</span>
        <span className="threat-overview-stat__value">{fmt(data.kevTotal)}</span>
        <span className="threat-overview-stat__sub">actively exploited</span>
      </div>
      <div className="threat-overview-stat">
        <span className="threat-overview-stat__label">High Severity</span>
        <span className="threat-overview-stat__value">{fmt(highSeverity)}</span>
        <span className="threat-overview-stat__sub">CVSS Critical + High</span>
      </div>
      <div className="threat-overview-stat">
        <span className="threat-overview-stat__label">Avg Risk Score</span>
        <span className="threat-overview-stat__value">
          {loading || !data.riskScoreStats ? "—" : `${Math.round(data.riskScoreStats.avg_risk)}%`}
        </span>
        <span className="threat-overview-stat__sub">composite CVSS + KEV</span>
      </div>

      <div className="threat-overview-vendors">
        <span className="threat-overview-vendors__title">Top Exploited Vendors</span>
        {topVendors.length === 0 ? (
          <span className="threat-overview-stat__sub">No vendor data available.</span>
        ) : (
          <ol className="threat-overview-vendors__list">
            {topVendors.map((v, i) => (
              <li key={v.vendor} className="threat-overview-vendors__item">
                <span>
                  <span className="threat-overview-vendors__rank">#{i + 1}</span>
                  {v.vendor}
                </span>
                <span>{Math.round(v.avg_risk)}%</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="threat-overview-glossary" aria-label="Glossary">
        {GLOSSARY.map((g) => (
          <div key={g.abbr} className="threat-overview-glossary__term">
            <span className="threat-overview-glossary__abbr">{g.abbr}</span>
            <span className="threat-overview-glossary__def">{g.def}</span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default ThreatOverviewWidget;
