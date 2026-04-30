import React, { useEffect, useMemo, useState } from 'react';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import { fetchExploitedVulns, fetchRiskScoredVulns, type ExploitedVulnItem } from '../../api/vulnerabilities';

function formatDate(input: string | null): string {
  if (!input) return 'Unknown';
  const d = new Date(input);
  if (Number.isNaN(d.getTime())) return input;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatEpss(score: number | null): string {
  if (score == null) return '—';
  if (score < 0.001) return '<0.1%';
  return `${(score * 100).toFixed(score < 0.01 ? 2 : 1)}%`;
}

const EmergingThreatsCard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recentKev, setRecentKev] = useState<ExploitedVulnItem[]>([]);
  const [riskPrioritized, setRiskPrioritized] = useState<ExploitedVulnItem[]>([]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      fetchExploitedVulns({ page: 1, pageSize: 8, sortBy: 'kev_date_added', sortOrder: 'desc' }),
      fetchRiskScoredVulns({ page: 1, pageSize: 20, sortBy: 'risk_score', sortOrder: 'desc' }),
    ])
      .then(([kevRes, riskRes]) => {
        if (!active) return;
        setRecentKev(kevRes.items);
        setRiskPrioritized(riskRes.items);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load emerging threats');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const risingVendors = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of riskPrioritized.slice(0, 15)) {
      const vendor = item.vendor?.trim() || 'Unknown vendor';
      counts.set(vendor, (counts.get(vendor) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([vendor, count]) => ({ vendor, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 3);
  }, [riskPrioritized]);

  const epssPrioritized = useMemo(
    () =>
      riskPrioritized
        .filter((item) => item.epss_score != null)
        .sort((a, b) => (b.epss_score ?? 0) - (a.epss_score ?? 0))
        .slice(0, 4),
    [riskPrioritized],
  );

  return (
    <div className="card emerging-threats-card">
      <span className="widget-title">Emerging Threats Feed</span>
      {loading ? (
        <WidgetSkeleton variant="chart" />
      ) : error ? (
        <p className="stat-chart-description">{error}</p>
      ) : (
        <div className="emerging-threats-content">
          <section>
            <p className="emerging-threats-section-title">Recently Added KEVs</p>
            <ul className="emerging-threats-list">
              {recentKev.slice(0, 4).map((item) => (
                <li key={`kev-${item.id}`}>
                  <code>{item.id}</code> added {formatDate(item.kev_date_added)}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <p className="emerging-threats-section-title">Rising Risk Patterns</p>
            <ul className="emerging-threats-list">
              {risingVendors.length === 0 ? (
                <li>No vendor concentration pattern detected.</li>
              ) : (
                risingVendors.map((entry) => (
                  <li key={`vendor-${entry.vendor}`}>
                    {entry.vendor}: {entry.count} high-risk items in current top set
                  </li>
                ))
              )}
            </ul>
          </section>

          <section>
            <p className="emerging-threats-section-title">EPSS-Prioritized Items</p>
            <ul className="emerging-threats-list">
              {epssPrioritized.length === 0 ? (
                <li>EPSS data not available yet.</li>
              ) : (
                epssPrioritized.map((item) => (
                  <li key={`epss-${item.id}`}>
                    <code>{item.id}</code> - EPSS {formatEpss(item.epss_score)} - Risk {item.risk_score?.toFixed(1) ?? '—'}
                  </li>
                ))
              )}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
};

export default EmergingThreatsCard;
