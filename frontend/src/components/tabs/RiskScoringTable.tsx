import React, { useState, useCallback, useEffect } from 'react';
import { useDebounce } from '../../hooks/useDebounce';
import { fetchWithAuth } from '../../api/fetchWithAuth';
import InfoTip from '../shared/InfoTip';

const RISK_SCORE_TIP =
    '0–100 composite combining CVSS severity, KEV presence, EPSS exploitation probability, and recency. Higher = more risk.';
const EPSS_TIP =
    'EPSS = Exploit Prediction Scoring System. Probability (0–100%) that this CVE will be exploited in the next 30 days.';

interface RiskScoredItem {
    id: string;
    vulnerability_name: string;
    vendor: string;
    product: string;
    severity_label: string;
    severity_score: number | null;
    risk_score: number | null;
    is_kev: boolean;
    kev_date_added: string;
    nvd_published?: string | null;
    epss_score?: number | null;
}

interface ApiResponse {
    total: number;
    page: number;
    page_size: number;
    items: RiskScoredItem[];
}

interface RiskBand {
    label: string;
    min: number;
    max: number;
    count: number;
}

interface TopVendor {
    vendor: string;
    avg_risk: number;
}

interface RiskStatsResponse {
    bands: RiskBand[];
    top_vendors: TopVendor[];
    avg_risk: number;
    total: number;
}

const PAGE_SIZE = 10;
type DataSourceFilter = 'all' | 'kev' | 'nvd';

interface Props {
    apiBaseUrl: string;
}

const RiskScoringTable: React.FC<Props> = ({ apiBaseUrl }) => {
    const [data, setData] = useState<RiskScoredItem[]>([]);
    const [stats, setStats] = useState<RiskStatsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [dataSource, setDataSource] = useState<DataSourceFilter>('all');
    const [searchInput, setSearchInput] = useState('');
    const debouncedSearch = useDebounce(searchInput);

    const fetchData = useCallback(async (p: number, source: DataSourceFilter, search?: string, signal?: AbortSignal) => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                page: String(p),
                page_size: String(PAGE_SIZE),
                sort_by: 'nvd_published',
                sort_order: 'desc',
                data_source: source,
            });
            if (search) params.set('search', search);
            const response = await fetchWithAuth(
                `${apiBaseUrl}/api/v1/vulnerabilities/risk-scored?${params}`,
                signal ? { signal } : undefined
            );
            if (!response.ok) throw new Error(`Failed to fetch risk scoring data: ${response.status}`);
            const result: ApiResponse = await response.json();
            setData(result.items);
            setTotal(result.total);
            setPage(p);
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            setError(err instanceof Error ? err.message : 'Error fetching risk data');
        } finally {
            setLoading(false);
        }
    }, [apiBaseUrl]);

    const fetchStats = useCallback(async (source: DataSourceFilter, signal?: AbortSignal) => {
        try {
            const params = new URLSearchParams({ data_source: source });
            const response = await fetchWithAuth(
                `${apiBaseUrl}/api/v1/vulnerabilities/risk-scored/stats?${params}`,
                signal ? { signal } : undefined
            );
            if (!response.ok) return;
            const result: RiskStatsResponse = await response.json();
            setStats(result);
        } catch {
            // Stats are supplementary; don't block the page on failure
        }
    }, [apiBaseUrl]);

    useEffect(() => {
        const controller = new AbortController();
        fetchData(1, dataSource, debouncedSearch, controller.signal);
        fetchStats(dataSource, controller.signal);
        return () => controller.abort();
    }, [fetchData, fetchStats, dataSource, debouncedSearch]);

    const BAND_COLORS: Record<string, string> = {
        'Critical (80-100)': '#dc2626',
        'High (60-79)': '#f59e0b',
        'Medium (40-59)': '#eab308',
        'Low (0-39)': '#3b82f6',
    };

    const riskBands = stats?.bands ?? [];
    const maxBandCount = Math.max(1, ...riskBands.map(b => b.count));
    const topVendorsByRisk = stats?.top_vendors ?? [];
    const maxVendorRisk = Math.max(1, ...topVendorsByRisk.map(v => v.avg_risk));
    const avgRiskScore = stats?.avg_risk ?? 0;

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    const getRiskBadgeStyle = (score: number) => ({
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '0.85em',
        fontWeight: 'bold' as const,
        background: score >= 80 ? '#7f1d1d' : score >= 60 ? '#92400e' : score >= 40 ? '#854d0e' : '#1e3a8a',
        color: score >= 80 ? '#fca5a5' : score >= 60 ? '#fbbf24' : score >= 40 ? '#fde047' : '#93c5fd',
        border: `1px solid ${score >= 80 ? '#991b1b' : score >= 60 ? '#b45309' : score >= 40 ? '#a16207' : '#1e40af'}`,
    });

    return (
        <div className="data-table-container">
            <h2>Risk Scoring - NVD + KEV Combined ({total} total)</h2>
            <div className="filter-controls">
                <div className="filter-group">
                    <label htmlFor="risk-search">CVE ID / Vulnerability</label>
                    <input
                        id="risk-search"
                        type="text"
                        placeholder="e.g. CVE-2021"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                    />
                </div>
                <div className="filter-group">
                    <label htmlFor="risk-source-filter">Data Source</label>
                    <select
                        id="risk-source-filter"
                        value={dataSource}
                        onChange={(e) => setDataSource(e.target.value as DataSourceFilter)}
                    >
                        <option value="all">All</option>
                        <option value="kev">KEV</option>
                        <option value="nvd">NVD</option>
                    </select>
                </div>
                <button
                    className="reset-filters-btn"
                    onClick={() => { setSearchInput(''); setDataSource('all'); }}
                >
                    Reset Filters
                </button>
            </div>
            <div className="pagination-info">
                Showing {data.length} of {total} vulnerabilities with calculated risk scores
            </div>
            {loading && <p>Loading risk scoring data...</p>}
            {error && <p className="error">Error: {error}</p>}

            {!loading && !error && data.length === 0 && (
                <div className="empty-state">
                    <p>No risk-scored vulnerabilities available.</p>
                </div>
            )}

            {data.length > 0 && (
                <>
                    <div className="risk-analytics-grid">
                        <div className="risk-analytics-card">
                            <h3>Risk Distribution</h3>
                            <div className="risk-bar-chart">
                                {riskBands.map((band) => (
                                    <div className="risk-bar-row" key={band.label}>
                                        <span className="risk-bar-label">{band.label}</span>
                                        <div className="risk-bar-track">
                                            <div
                                                className="risk-bar-fill"
                                                style={{
                                                    width: `${(band.count / maxBandCount) * 100}%`,
                                                    backgroundColor: BAND_COLORS[band.label] ?? '#3b82f6',
                                                }}
                                            />
                                        </div>
                                        <span className="risk-bar-value">{band.count}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="risk-analytics-card">
                            <h3>Top Vendors by Avg Risk</h3>
                            <div className="risk-bar-chart">
                                {topVendorsByRisk.map((vendor) => (
                                    <div className="risk-bar-row" key={vendor.vendor}>
                                        <span className="risk-bar-label">{vendor.vendor}</span>
                                        <div className="risk-bar-track">
                                            <div
                                                className="risk-bar-fill risk-bar-fill-vendor"
                                                style={{ width: `${(vendor.avg_risk / maxVendorRisk) * 100}%` }}
                                            />
                                        </div>
                                        <span className="risk-bar-value">{vendor.avg_risk.toFixed(1)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="risk-kpi-card">
                            <div className="risk-kpi-label">
                                Average Risk
                                <InfoTip text={RISK_SCORE_TIP} label="Average Risk" />
                            </div>
                            <div className="risk-kpi-value">{avgRiskScore.toFixed(1)}</div>
                            <div className="risk-kpi-subtitle">out of 100</div>
                        </div>
                    </div>

                    <div className="table-scroll-wrapper">
                    <table className="data-table cisa-table">
                        <thead>
                            <tr>
                                <th>CVE ID</th>
                                <th>Data Source</th>
                                <th>Vulnerability</th>
                                <th>CVSS Score</th>
                                <th>
                                    Risk Score
                                    <InfoTip text={RISK_SCORE_TIP} label="Risk Score" />
                                </th>
                                <th>
                                    EPSS
                                    <InfoTip text={EPSS_TIP} label="EPSS" />
                                </th>
                                <th>Published</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((item) => (
                                <tr key={item.id}>
                                    <td className="cve-id">
                                        <a href={`https://nvd.nist.gov/vuln/detail/${item.id}`} target="_blank" rel="noopener noreferrer">
                                            {item.id}
                                        </a>
                                    </td>
                                    <td>
                                        <span style={{
                                            padding: '3px 8px',
                                            borderRadius: '3px',
                                            fontSize: '0.8em',
                                            fontWeight: '600',
                                            background: item.is_kev ? '#dc2626' : '#475569',
                                            color: 'white'
                                        }}>
                                            {item.is_kev ? 'KEV' : 'NVD'}
                                        </span>
                                    </td>
                                    <td className="vuln-name">{item.vulnerability_name.substring(0, 100)}...</td>
                                    <td>{item.severity_score ?? 'N/A'}</td>
                                    <td>
                                        {item.risk_score !== null && item.risk_score !== undefined ? (
                                            <span style={getRiskBadgeStyle(item.risk_score)}>
                                                {item.risk_score.toFixed(1)}/100
                                            </span>
                                        ) : 'N/A'}
                                    </td>
                                    <td>
                                        {item.epss_score != null ? (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                <div style={{
                                                    width: 40, height: 6, borderRadius: 3,
                                                    background: '#e5e7eb', overflow: 'hidden',
                                                }}>
                                                    <div style={{
                                                        width: `${Math.max(2, item.epss_score * 100)}%`,
                                                        height: '100%',
                                                        background: item.epss_score >= 0.7 ? '#dc2626'
                                                            : item.epss_score >= 0.3 ? '#d97706' : '#6b7280',
                                                        borderRadius: 3,
                                                    }} />
                                                </div>
                                                <span style={{ fontSize: 12, fontWeight: 600 }}>
                                                    {item.epss_score < 0.001
                                                        ? '<0.1%'
                                                        : `${(item.epss_score * 100).toFixed(item.epss_score < 0.01 ? 2 : 1)}%`}
                                                </span>
                                            </div>
                                        ) : '—'}
                                    </td>
                                    <td>{item.nvd_published || 'N/A'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    </div>
                    <div className="pagination-controls">
                        <button
                            disabled={page === 1}
                            onClick={() => fetchData(page - 1, dataSource, debouncedSearch)}
                        >
                            &larr; Previous
                        </button>
                        <span>Page {page} of {totalPages}</span>
                        <button
                            disabled={page >= totalPages}
                            onClick={() => fetchData(page + 1, dataSource, debouncedSearch)}
                        >
                            Next &rarr;
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default RiskScoringTable;
