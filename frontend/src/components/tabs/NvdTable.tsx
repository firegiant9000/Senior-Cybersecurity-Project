import React, { useState, useEffect, useCallback } from 'react';
import { downloadCsv } from '../../utils/csvExport';
import { useDebounce } from '../../hooks/useDebounce';
import { fetchWithAuth } from '../../api/fetchWithAuth';
import SeverityDistributionChart from '../charts/SeverityDistributionChart';

interface NVDCVEItem {
    id: string;
    description: string;
    severity_label: string;
    severity_score: number | null;
    published_date: string;
    last_modified: string;
}

interface ApiResponse {
    total: number;
    page: number;
    page_size: number;
    items: NVDCVEItem[];
}

const PAGE_SIZE = 10;
const SEVERITY_OPTIONS = ['Critical', 'High', 'Medium', 'Low', 'Unknown'] as const;

interface Props {
    apiBaseUrl: string;
}

const NvdTable: React.FC<Props> = ({ apiBaseUrl }) => {
    const [data, setData] = useState<NVDCVEItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    // Filter state
    const [searchInput, setSearchInput] = useState('');
    const [selectedSeverities, setSelectedSeverities] = useState<Set<string>>(new Set());
    const debouncedSearch = useDebounce(searchInput);

    // Build comma-separated severity string for the API (empty = all)
    const severityParam = selectedSeverities.size > 0
        ? Array.from(selectedSeverities).join(',')
        : '';

    const toggleSeverity = (sev: string) => {
        setSelectedSeverities((prev) => {
            const next = new Set(prev);
            if (next.has(sev)) {
                next.delete(sev);
            } else {
                next.add(sev);
            }
            return next;
        });
    };

    const fetchData = useCallback(async (p: number, search: string, sev: string, signal?: AbortSignal) => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                page: String(p),
                page_size: String(PAGE_SIZE),
            });
            if (search) params.set('search', search);
            if (sev) params.set('severity', sev);

            const url = `${apiBaseUrl}/api/v1/nvd/cves?${params}`;
            const response = await fetchWithAuth(url, signal ? { signal } : undefined);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to fetch NVD data: ${response.status} - ${errorText}`);
            }
            const result: ApiResponse = await response.json();
            setData(result.items);
            setTotal(result.total);
            setPage(p);
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            const errorMsg = err instanceof Error ? err.message : 'Unknown error fetching data';
            console.error('NVD fetch error:', errorMsg);
            setError(errorMsg);
        } finally {
            setLoading(false);
        }
    }, [apiBaseUrl]);

    // Reset to page 1 when filters change
    useEffect(() => {
        const controller = new AbortController();
        fetchData(1, debouncedSearch, severityParam, controller.signal);
        return () => controller.abort();
    }, [debouncedSearch, severityParam, fetchData]);

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    return (
        <div className="data-table-container">
            <SeverityDistributionChart apiBaseUrl={apiBaseUrl} search={debouncedSearch} severity={severityParam} />
            <h2>NVD - National Vulnerability Database ({total} total)</h2>

            <div className="filter-controls">
                <div className="filter-group">
                    <label htmlFor="nvd-search">CVE ID / Description</label>
                    <input
                        id="nvd-search"
                        type="text"
                        placeholder="e.g. CVE-2025"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                    />
                </div>
                <div className="filter-group">
                    <label>Severity</label>
                    <div className="severity-checkboxes">
                        {SEVERITY_OPTIONS.map((sev) => (
                            <label key={sev} className={`severity-chip ${selectedSeverities.has(sev) ? 'active' : ''}`}>
                                <input
                                    type="checkbox"
                                    checked={selectedSeverities.has(sev)}
                                    onChange={() => toggleSeverity(sev)}
                                />
                                {sev}
                            </label>
                        ))}
                    </div>
                </div>
                <button
                    className="reset-filters-btn"
                    onClick={() => { setSearchInput(''); setSelectedSeverities(new Set()); }}
                >
                    Reset Filters
                </button>
            </div>

            <div className="table-toolbar">
                <div className="pagination-info">Showing {data.length} of {total}</div>
                <button
                    className="export-csv-btn"
                    disabled={data.length === 0}
                    onClick={() => downloadCsv(
                        'nvd-cves.csv',
                        ['CVE ID', 'Description', 'Severity', 'Score', 'Published', 'Last Modified'],
                        data.map(r => [r.id, r.description, r.severity_label, r.severity_score, r.published_date, r.last_modified]),
                    )}
                >
                    Export CSV
                </button>
            </div>
            {loading && <p>Loading NVD CVE data...</p>}
            {error && <p className="error">Error: {error}</p>}

            {!loading && !error && data.length === 0 && (
                <div className="empty-state">
                    <p>No CVEs found matching your filters. Try adjusting your search or severity filter.</p>
                </div>
            )}

            {data.length > 0 && (
                <>
                    <div className="table-scroll-wrapper">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>CVE ID</th>
                                    <th>Description</th>
                                    <th>Severity</th>
                                    <th>Score</th>
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
                                        <td>{item.description.substring(0, 80)}...</td>
                                        <td>{item.severity_label || 'Unknown'}</td>
                                        <td>{item.severity_score || 'N/A'}</td>
                                        <td>{item.published_date}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="pagination-controls">
                        <button disabled={page === 1} onClick={() => fetchData(page - 1, debouncedSearch, severityParam)}>
                            &larr; Previous
                        </button>
                        <span>Page {page} of {totalPages}</span>
                        <button disabled={page >= totalPages} onClick={() => fetchData(page + 1, debouncedSearch, severityParam)}>
                            Next &rarr;
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default NvdTable;
