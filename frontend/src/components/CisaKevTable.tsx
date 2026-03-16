import React, { useState, useEffect, useCallback } from 'react';
import { useDebounce } from '../hooks/useDebounce';

import { PieChart, Pie, Tooltip, Legend, ResponsiveContainer, Sector} from 'recharts';

interface CISAVulnerability {
    id: string;
    vulnerability_name: string;
    vendor: string;
    product: string;
    severity_label: string | null;
    severity_score: number | null;
    is_kev: boolean;
    kev_date_added: string;
}

interface ApiResponse {
    total: number;
    page: number;
    page_size: number;
    items: CISAVulnerability[];
}

const PAGE_SIZE = 10;
const SEVERITY_OPTIONS = ['All', 'Critical', 'High', 'Medium', 'Low', 'Unknown'];
const CANONICAL_SEVERITIES = new Set(['Critical', 'High', 'Medium', 'Low', 'Unknown']);

function normalizeSeverity(value: string | null | undefined): string {
    const raw = (value || '').trim();
    if (!raw) return 'Unknown';
    const normalized = `${raw.charAt(0).toUpperCase()}${raw.slice(1).toLowerCase()}`;
    return CANONICAL_SEVERITIES.has(normalized) ? normalized : 'Unknown';
}

const SEVERITY_COLORS: Record<string, string> = {
    'Critical': '#d32f2f', // Red
    'High': '#f57c00', // Orange
    'Medium': '#fbc02d', // Yellow
    'Low': '#388e3c', // Green
    'Unknown': '#9e9e9e' // Grey

};

interface Props {
    apiBaseUrl: string;
}

const CisaKevTable: React.FC<Props> = ({ apiBaseUrl }) => {
    const [data, setData] = useState<CISAVulnerability[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    // Filter state
    const [searchInput, setSearchInput] = useState('');
    const [severity, setSeverity] = useState('All');
    const debouncedSearch = useDebounce(searchInput);

    const fetchData = useCallback(async (p: number, search: string, sev: string, signal?: AbortSignal) => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                page: String(p),
                page_size: String(PAGE_SIZE),
                sort_by: 'kev_date_added',
                sort_order: 'desc',
            });
            if (search) params.set('search', search);
            if (sev !== 'All') params.set('severity', sev);

            const response = await fetch(`${apiBaseUrl}/api/v1/vulnerabilities/exploited?${params}`, signal ? { signal } : undefined);
            if (!response.ok) throw new Error(`Failed to fetch CISA KEV data: ${response.status}`);
            const result: ApiResponse = await response.json();

            // Safety net: if the backend ignores severity for any reason,
            // enforce the selected severity on the current page response.
            const selectedSeverity = normalizeSeverity(sev);
            const filteredItems = selectedSeverity === 'Unknown'
                ? (sev === 'All'
                    ? result.items
                    : result.items.filter((item) => normalizeSeverity(item.severity_label) === 'Unknown'))
                : (sev === 'All'
                    ? result.items
                    : result.items.filter((item) => normalizeSeverity(item.severity_label) === selectedSeverity));

            const backendHonoredFilter =
                sev === 'All' || filteredItems.length === result.items.length;

            setData(filteredItems);
            setTotal(backendHonoredFilter ? result.total : filteredItems.length);
            setPage(p);
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            const errorMsg = err instanceof Error ? err.message : 'Error fetching data';
            console.error('CISA KEV fetch error:', errorMsg);
            setError(errorMsg);
        } finally {
            setLoading(false);
        }
    }, [apiBaseUrl]);

    // Reset to page 1 when filters change
    useEffect(() => {
        const controller = new AbortController();
        setData([]);
        setTotal(0);
        fetchData(1, debouncedSearch, severity, controller.signal);
        return () => controller.abort();
    }, [debouncedSearch, severity, fetchData]);

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    // ADDED CODE FOR PIE CHART
    const severityCounts = data.reduce((acc, curr) => {
        const sev = curr.severity_label || 'Unknown';
        acc[sev] = (acc[sev] || 0) + 1;
        return acc;
    }, {} as Record<string, number>);

    const pieChartData = Object.keys(severityCounts).map(key => ({
        name: key,
        value: severityCounts[key],
        fill: SEVERITY_COLORS[key] || SEVERITY_COLORS['Unknown']

    }));
    

    return (
        <div className="data-table-container">
            <h2>CISA KEV - Exploited Vulnerabilities ({total} total)</h2>

            <div className="filter-controls">
                <div className="filter-group">
                    <label htmlFor="cisa-search">CVE ID</label>
                    <input
                        id="cisa-search"
                        type="text"
                        placeholder="e.g. CVE-2021"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                    />
                </div>
                <div className="filter-group">
                    <label htmlFor="cisa-severity">Severity</label>
                    <select
                        id="cisa-severity"
                        value={severity}
                        onChange={(e) => setSeverity(e.target.value)}
                    >
                        {SEVERITY_OPTIONS.map((opt) => (
                            <option key={opt} value={opt}>{opt}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="pagination-info">Showing {data.length} of {total}</div>
            {loading && <p>Loading CISA KEV data...</p>}
            {error && <p className="error">Error: {error}</p>}

            {!loading && !error && data.length === 0 && (
                <div className="empty-state">
                    <p>No CISA KEV vulnerabilities found matching your filters. Try adjusting your search or severity filter.</p>
                </div>
            )}

            {!error && data.length > 0 && (
                <>
                    <div className=" severity-chart-container">
                        <h3>Severity Distribution (Current Page)</h3>
                        <p className="severity-chart-total">Showing {data.length} vulnerabilities and their severity breakdown below.</p>
                        <div style={{ width: '100%', height: 300}}>
                            <ResponsiveContainer>
                                <PieChart>
                                    <Tooltip />
                                    <Legend />
                                    <Pie
                                        data={pieChartData}
                                        cx="50%"
                                        cy="50%"
                                        outerRadius={100}
                                        fill="#8884d8"
                                        dataKey="value"
                                        label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
                                    
                                        shape={(props: any) => (

                                        
                                            <Sector
                                                {...props}
                                                fill={SEVERITY_COLORS[props.name] || SEVERITY_COLORS['Unknown']}
                                            />
                                        )}
                            
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <table className="data-table cisa-table">
                        <thead>
                            <tr>
                                <th>CVE ID</th>
                                <th>Severity</th>
                                <th>Score</th>
                                <th>Vendor</th>
                                <th>Product</th>
                                <th>Vulnerability</th>
                                <th>Date Added</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((item) => (
                                <tr key={item.id}>
                                    <td className="cve-id">
                                        <a href={`https://www.cve.org/CVERecord?id=${item.id}`} target="_blank" rel="noopener noreferrer">
                                            {item.id}
                                        </a>
                                    </td>
                                    <td>{item.severity_label || 'Unknown'}</td>
                                    <td>{item.severity_score ?? 'N/A'}</td>
                                    <td>{item.vendor}</td>
                                    <td>{item.product}</td>
                                    <td className="vuln-name">{item.vulnerability_name.substring(0, 100)}...</td>
                                    <td>{item.kev_date_added}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <div className="pagination-controls">
                        <button disabled={page === 1} onClick={() => fetchData(page - 1, debouncedSearch, severity)}>
                            &larr; Previous
                        </button>
                        <span>Page {page} of {totalPages}</span>
                        <button disabled={page >= totalPages} onClick={() => fetchData(page + 1, debouncedSearch, severity)}>
                            Next &rarr;
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default CisaKevTable;
