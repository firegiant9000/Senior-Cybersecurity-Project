import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  fetchIC3Anomalies,
  fetchTrendAnomalies,
  fetchVendorAnomalies,
  IC3AnomalyResponse,
  TrendAnomalyResponse,
  VendorAnomalyResponse,
} from '../../api/anomalies';

type SubTab = 'ic3' | 'trends' | 'vendors';

function pct(val: number | null): string {
  if (val === null) return '—';
  const sign = val >= 0 ? '+' : '';
  return `${sign}${(val * 100).toFixed(1)}%`;
}

function zColor(z: number): string {
  const abs = Math.abs(z);
  if (abs >= 3) return '#d32f2f';
  if (abs >= 2) return '#f57c00';
  return '#2e7d32';
}

const AnomaliesTab: React.FC = () => {
  const { user } = useAuth();
  const [subTab, setSubTab] = useState<SubTab>('ic3');

  const [ic3Data, setIC3Data] = useState<IC3AnomalyResponse | null>(null);
  const [trendsData, setTrendsData] = useState<TrendAnomalyResponse | null>(null);
  const [vendorData, setVendorData] = useState<VendorAnomalyResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (tab: SubTab) => {
    if (!user) return;
    setLoading(true);
    setError('');
    try {
      if (tab === 'ic3' && !ic3Data) {
        setIC3Data(await fetchIC3Anomalies());
      } else if (tab === 'trends' && !trendsData) {
        setTrendsData(await fetchTrendAnomalies());
      } else if (tab === 'vendors' && !vendorData) {
        setVendorData(await fetchVendorAnomalies());
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [user, ic3Data, trendsData, vendorData]);

  useEffect(() => { load(subTab); }, [subTab, load]);

  if (!user) {
    return <div className="tab-page"><p>Please log in to view anomaly detection.</p></div>;
  }

  const subTabStyle = (id: SubTab): React.CSSProperties => ({
    padding: '6px 14px',
    borderRadius: 6,
    border: 'none',
    cursor: 'pointer',
    fontWeight: subTab === id ? 700 : 400,
    background: subTab === id ? 'var(--accent, #3b82f6)' : 'var(--card-bg, #ffffff)',
    color: subTab === id ? '#fff' : 'var(--text-secondary, #555)',
    fontSize: 13,
  });

  return (
    <div className="tab-page">
      <div style={{ marginBottom: '1rem' }}>
        <h2 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 700 }}>Anomaly Detection</h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary, #555)' }}>
          Statistical outliers in IC3 incident data and vendor KEV exposure.
        </p>
      </div>

      {/* Sub-tab bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: '1.25rem' }}>
        <button style={subTabStyle('ic3')} onClick={() => setSubTab('ic3')}>IC3 State Anomalies</button>
        <button style={subTabStyle('trends')} onClick={() => setSubTab('trends')}>YoY Trends</button>
        <button style={subTabStyle('vendors')} onClick={() => setSubTab('vendors')}>Vendor Exposure</button>
      </div>

      {loading && <p style={{ color: 'var(--text-secondary, #555)', fontSize: 13 }}>Loading...</p>}
      {error && <p style={{ color: '#d32f2f' }}>{error}</p>}

      {/* IC3 Anomalies */}
      {subTab === 'ic3' && !loading && ic3Data && (
        <>
          <p style={{ fontSize: 13, color: 'var(--text-secondary, #555)', marginBottom: '0.75rem' }}>
            {ic3Data.total} state/sector combinations flagged at z-score ≥ {ic3Data.threshold}.
            Z-scores compare each state's incident rate against all states in the same sector and year.
          </p>
          {ic3Data.total === 0 ? (
            <p style={{ color: '#2e7d32' }}>No anomalies detected at the current threshold.</p>
          ) : (
            <div className="table-scroll-wrapper">
              <table className="tab-table">
                <thead>
                  <tr>
                    <th style={{ padding: '6px 8px' }}>Sector</th>
                    <th style={{ padding: '6px 8px' }}>State</th>
                    <th style={{ padding: '6px 8px' }}>Year</th>
                    <th style={{ padding: '6px 8px' }}>Complaints</th>
                    <th style={{ padding: '6px 8px' }}>Loss ($)</th>
                    <th style={{ padding: '6px 8px' }}>Z (Complaints)</th>
                    <th style={{ padding: '6px 8px' }}>Z (Loss)</th>
                    <th style={{ padding: '6px 8px' }}>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {ic3Data.items.map((item, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border, #334155)' }}>
                      <td style={{ padding: '6px 8px' }}>{item.sector}</td>
                      <td style={{ padding: '6px 8px', fontWeight: 600 }}>{item.state}</td>
                      <td style={{ padding: '6px 8px' }}>{item.year}</td>
                      <td style={{ padding: '6px 8px' }}>{item.complaint_count.toLocaleString()}</td>
                      <td style={{ padding: '6px 8px' }}>${item.loss_amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                      <td style={{ padding: '6px 8px', color: zColor(item.z_score_complaints), fontWeight: 700 }}>
                        {item.z_score_complaints.toFixed(2)}
                      </td>
                      <td style={{ padding: '6px 8px', color: zColor(item.z_score_loss), fontWeight: 700 }}>
                        {item.z_score_loss.toFixed(2)}
                      </td>
                      <td style={{ padding: '6px 8px', textTransform: 'capitalize' }}>{item.anomaly_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* YoY Trends */}
      {subTab === 'trends' && !loading && trendsData && (
        <>
          <p style={{ fontSize: 13, color: 'var(--text-secondary, #555)', marginBottom: '0.75rem' }}>
            Year-over-year change in IC3 incident totals by sector. Rows flagged when change exceeds ±{(trendsData.threshold_pct * 100).toFixed(0)}%.
          </p>
          <div className="table-scroll-wrapper">
            <table className="tab-table">
              <thead>
                <tr>
                  <th style={{ padding: '6px 8px' }}>Sector</th>
                  <th style={{ padding: '6px 8px' }}>Year</th>
                  <th style={{ padding: '6px 8px' }}>Complaints</th>
                  <th style={{ padding: '6px 8px' }}>Loss ($)</th>
                  <th style={{ padding: '6px 8px' }}>YoY Complaints</th>
                  <th style={{ padding: '6px 8px' }}>YoY Loss</th>
                  <th style={{ padding: '6px 8px' }}>Flagged</th>
                </tr>
              </thead>
              <tbody>
                {trendsData.items.map((item, i) => (
                  <tr
                    key={i}
                    style={{
                      borderBottom: '1px solid var(--border, #334155)',
                      background: item.flagged ? 'rgba(245, 124, 0, 0.07)' : undefined,
                    }}
                  >
                    <td style={{ padding: '6px 8px' }}>{item.sector}</td>
                    <td style={{ padding: '6px 8px' }}>{item.year}</td>
                    <td style={{ padding: '6px 8px' }}>{item.complaint_count.toLocaleString()}</td>
                    <td style={{ padding: '6px 8px' }}>${item.loss_amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                    <td style={{
                      padding: '6px 8px',
                      fontWeight: item.yoy_change_complaints !== null ? 600 : 400,
                      color: item.yoy_change_complaints !== null
                        ? item.yoy_change_complaints > 0 ? '#d32f2f' : '#2e7d32'
                        : undefined,
                    }}>
                      {pct(item.yoy_change_complaints)}
                    </td>
                    <td style={{
                      padding: '6px 8px',
                      fontWeight: item.yoy_change_loss !== null ? 600 : 400,
                      color: item.yoy_change_loss !== null
                        ? item.yoy_change_loss > 0 ? '#d32f2f' : '#2e7d32'
                        : undefined,
                    }}>
                      {pct(item.yoy_change_loss)}
                    </td>
                    <td style={{ padding: '6px 8px' }}>
                      {item.flagged ? <span style={{ color: '#f57c00', fontWeight: 700 }}>⚠ Yes</span> : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Vendor Exposure */}
      {subTab === 'vendors' && !loading && vendorData && (
        <>
          {!vendorData.has_vendors ? (
            <p style={{ color: 'var(--text-secondary, #555)' }}>
              No vendors configured. Add your technology stack in Organization Profile to see exposure analysis.
            </p>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: 'var(--text-secondary, #555)' }}>Your total KEV matches: </span>
                  <strong>{vendorData.org_total_matches}</strong>
                </div>
                <div style={{ fontSize: 13 }}>
                  <span style={{ color: 'var(--text-secondary, #555)' }}>Global avg (same # vendors): </span>
                  <strong>{vendorData.global_avg_total.toFixed(1)}</strong>
                </div>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary, #555)', marginBottom: '0.75rem' }}>
                Z-scores compare each vendor's KEV match count to the distribution across all orgs.
                Vendors flagged at z-score ≥ {vendorData.threshold}.
              </p>
              {vendorData.items.length === 0 ? (
                <p style={{ color: '#2e7d32' }}>No vendor exposure anomalies detected.</p>
              ) : (
                <div className="table-scroll-wrapper">
                  <table className="tab-table">
                    <thead>
                      <tr>
                        <th style={{ padding: '6px 8px' }}>Vendor</th>
                        <th style={{ padding: '6px 8px' }}>KEV Matches</th>
                        <th style={{ padding: '6px 8px' }}>Global Avg</th>
                        <th style={{ padding: '6px 8px' }}>Z-Score</th>
                        <th style={{ padding: '6px 8px' }}>Anomaly</th>
                      </tr>
                    </thead>
                    <tbody>
                      {vendorData.items.map((item, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border, #334155)' }}>
                          <td style={{ padding: '6px 8px', fontWeight: 600 }}>{item.vendor_name}</td>
                          <td style={{ padding: '6px 8px' }}>{item.kev_match_count}</td>
                          <td style={{ padding: '6px 8px' }}>{item.global_avg_matches.toFixed(1)}</td>
                          <td style={{ padding: '6px 8px', color: zColor(item.z_score), fontWeight: 700 }}>
                            {item.z_score.toFixed(2)}
                          </td>
                          <td style={{ padding: '6px 8px' }}>
                            {item.anomaly
                              ? <span style={{ color: '#d32f2f', fontWeight: 700 }}>⚠ High exposure</span>
                              : <span style={{ color: '#2e7d32' }}>Normal</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
};

export default AnomaliesTab;
