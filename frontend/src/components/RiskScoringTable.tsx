import React, { useState, useCallback, useEffect, useMemo } from 'react';

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
}

interface ApiResponse {
    total: number;
    page: number;
    page_size: number;
    items: RiskScoredItem[];
}

const PAGE_SIZE = 10;
type DataSourceFilter = 'all' | 'kev' | 'nvd';

interface Props {
    apiBaseUrl: string;
}

const RiskScoringTable: React.FC<Props> = ({ apiBaseUrl }) => {
    const [data, setData] = useState<RiskScoredItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [dataSource, setDataSource] = useState<DataSourceFilter>('all');

    const fetchData = useCallback(async (p: number, source: DataSourceFilter, signal?: AbortSignal) => {
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
            const response = await fetch(
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

    useEffect(() => {
        const controller = new AbortController();
        fetchData(1, dataSource, controller.signal);
        return () => controller.abort();
    }, [fetchData, dataSource]);

    const riskBands = useMemo(() => {
        const bands = [
            { label: 'Critical (80-100)', color: '#dc2626', min: 80, max: 100, count: 0 },
            { label: 'High (60-79)', color: '#f59e0b', min: 60, max: 79, count: 0 },
            { label: 'Medium (40-59)', color: '#eab308', min: 40, max: 59, count: 0 },
            { label: 'Low (0-39)', color: '#3b82f6', min: 0, max: 39, count: 0 },
        ];
        for (const item of data) {
            const score = item.risk_score ?? 0;
            for (const band of bands) {
                if (score >= band.min && score <= band.max) {
                    band.count++;
                    break;
                }
            }
        }
        return bands;
    }, [data]);

    const maxBandCount = useMemo(() => Math.max(1, ...riskBands.map(b => b.count)), [riskBands]);

    const topVendorsByRisk = useMemo(() => {
        const vendorMap: Record<string, { total: number; count: number }> = {};
        for (const item of data) {
            const v = item.vendor || 'Unknown';
            if (!vendorMap[v]) vendorMap[v] = { total: 0, count: 0 };
            vendorMap[v].total += item.risk_score ?? 0;
            vendorMap[v].count++;
        }
        return Object.entries(vendorMap)
            .map(([vendor, { total: t, count }]) => ({ vendor, avgRisk: t / count }))
            .sort((a, b) => b.avgRisk - a.avgRisk)
            .slice(0, 5);
    }, [data]);

    const maxVendorRisk = useMemo(() => Math.max(1, ...topVendorsByRisk.map(v => v.avgRisk)), [topVendorsByRisk]);

    const avgRiskScore = useMemo(() => {
        if (data.length === 0) return 0;
        const sum = data.reduce((acc, item) => acc + (item.risk_score ?? 0), 0);
        return sum / data.length;
    }, [data]);

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
                                                    backgroundColor: band.color,
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
                                                style={{ width: `${(vendor.avgRisk / maxVendorRisk) * 100}%` }}
                                            />
                                        </div>
                                        <span className="risk-bar-value">{vendor.avgRisk.toFixed(1)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="risk-kpi-card">
                            <div className="risk-kpi-label">Average Risk (page)</div>
                            <div className="risk-kpi-value">{avgRiskScore.toFixed(1)}</div>
                            <div className="risk-kpi-subtitle">out of 100</div>
                        </div>
                    </div>

                    <table className="data-table cisa-table">
                        <thead>
                            <tr>
                                <th>CVE ID</th>
                                <th>Data Source</th>
                                <th>Vulnerability</th>
                                <th>CVSS Score</th>
                                <th>Risk Score</th>
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
                                    <td>{item.nvd_published || 'N/A'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <div className="pagination-controls">
                        <button
                            disabled={page === 1}
                            onClick={() => fetchData(page - 1, dataSource)}
                        >
                            &larr; Previous
                        </button>
                        <span>Page {page} of {totalPages}</span>
                        <button
                            disabled={page >= totalPages}
                            onClick={() => fetchData(page + 1, dataSource)}
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
