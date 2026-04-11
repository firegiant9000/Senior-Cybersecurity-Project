import React, { useState, useEffect, useCallback } from 'react';
import { useDebounce } from '../../hooks/useDebounce';
import { downloadCsv } from '../../utils/csvExport';
import { fetchWithAuth } from '../../api/fetchWithAuth';

interface IC3IncidentItem {
    id: number;
    year: number;
    attack_type: string;
    sector: string;
    state: string;
    complaint_count: number;
    loss_amount: number;
    avg_loss_per_incident: number;
}

interface ApiResponse {
    total: number;
    page: number;
    page_size: number;
    items: IC3IncidentItem[];
}

interface FilterOptions {
    attack_types: string[];
    states: string[];
    years: number[];
}

const PAGE_SIZE = 10;

interface Props {
    apiBaseUrl: string;
}

const IC3Table: React.FC<Props> = ({ apiBaseUrl }) => {
    const [data, setData] = useState<IC3IncidentItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    // Filter state
    const [searchInput, setSearchInput] = useState('');
    const [attackType, setAttackType] = useState('All');
    const [state, setState] = useState('All');
    const [year, setYear] = useState('All');
    const debouncedSearch = useDebounce(searchInput);

    // Dropdown options from the server
    const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);

    // Fetch filter options once on mount
    useEffect(() => {
        const controller = new AbortController();
        const loadOptions = async () => {
            try {
                const response = await fetchWithAuth(`${apiBaseUrl}/api/v1/ic3/filter-options`, {
                    signal: controller.signal,
                });
                if (response.ok) {
                    const options: FilterOptions = await response.json();
                    setFilterOptions(options);
                } else {
                    console.error('IC3 filter-options failed:', response.status, response.statusText);
                }
            } catch (err) {
                if (err instanceof DOMException && err.name === 'AbortError') return;
                console.error('IC3 filter-options fetch error:', err);
            }
        };
        loadOptions();
        return () => controller.abort();
    }, [apiBaseUrl]);

    const fetchData = useCallback(async (p: number, search: string, at: string, st: string, yr: string, signal?: AbortSignal) => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                page: String(p),
                page_size: String(PAGE_SIZE),
                sort_by: 'loss_amount',
                sort_order: 'desc',
            });
            if (search) params.set('search', search);
            if (at !== 'All') params.set('attack_type', at);
            if (st !== 'All') params.set('state', st);
            if (yr !== 'All') params.set('year', yr);

            const response = await fetchWithAuth(`${apiBaseUrl}/api/v1/ic3/incidents?${params}`, signal ? { signal } : undefined);
            if (!response.ok) throw new Error(`Failed to fetch IC3 data: ${response.status}`);
            const result: ApiResponse = await response.json();
            setData(result.items);
            setTotal(result.total);
            setPage(p);
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            const errorMsg = err instanceof Error ? err.message : 'Error fetching IC3 data';
            console.error('IC3 fetch error:', errorMsg);
            setError(errorMsg);
        } finally {
            setLoading(false);
        }
    }, [apiBaseUrl]);

    // Reset to page 1 when filters change
    useEffect(() => {
        const controller = new AbortController();
        fetchData(1, debouncedSearch, attackType, state, year, controller.signal);
        return () => controller.abort();
    }, [debouncedSearch, attackType, state, year, fetchData]);

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    return (
        <div className="tab-content">
            <h2>IC3 - FBI Internet Crime Complaints</h2>

            <div className="filter-controls">
                <div className="filter-group">
                    <label htmlFor="ic3-search">Search</label>
                    <input
                        id="ic3-search"
                        type="text"
                        placeholder="e.g. Ransomware, Finance"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                    />
                </div>
                <div className="filter-group">
                    <label htmlFor="ic3-attack-type">Attack Type</label>
                    <select
                        id="ic3-attack-type"
                        value={attackType}
                        onChange={(e) => setAttackType(e.target.value)}
                    >
                        <option value="All">All</option>
                        {filterOptions?.attack_types.map((at) => (
                            <option key={at} value={at}>{at}</option>
                        ))}
                    </select>
                </div>
                <div className="filter-group">
                    <label htmlFor="ic3-state">State</label>
                    <select
                        id="ic3-state"
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                    >
                        <option value="All">All</option>
                        {filterOptions?.states.map((st) => (
                            <option key={st} value={st}>{st}</option>
                        ))}
                    </select>
                </div>
                <div className="filter-group">
                    <label htmlFor="ic3-year">Year</label>
                    <select
                        id="ic3-year"
                        value={year}
                        onChange={(e) => setYear(e.target.value)}
                    >
                        <option value="All">All</option>
                        {filterOptions?.years.map((yr) => (
                            <option key={yr} value={String(yr)}>{yr}</option>
                        ))}
                    </select>
                </div>
                <button
                    className="reset-filters-btn"
                    onClick={() => { setSearchInput(''); setAttackType('All'); setState('All'); setYear('All'); }}
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
                        'ic3-incidents.csv',
                        ['Year', 'Attack Type', 'Sector', 'State', 'Complaints', 'Total Loss', 'Avg Loss/Incident'],
                        data.map(r => [r.year, r.attack_type, r.sector, r.state, r.complaint_count, r.loss_amount, r.avg_loss_per_incident]),
                    )}
                >
                    Export CSV
                </button>
            </div>
            {loading && <div className="loading">Loading IC3 incidents...</div>}
            {error && <div className="error">Error: {error}</div>}

            {!loading && !error && data.length === 0 && (
                <div className="empty-state">
                    <p>No IC3 incidents found. {attackType !== 'All' || state !== 'All' || year !== 'All'
                        ? 'Try adjusting your filters.' : 'Run the ingestion script:'}</p>
                    {attackType === 'All' && state === 'All' && year === 'All' && (
                        <code>python scripts/ingest_ic3_enhanced.py</code>
                    )}
                </div>
            )}

            {!loading && !error && data.length > 0 && (
                <>
                    <div className="summary-stats">
                        <div className="stat-card">
                            <div className="stat-label">Filtered Records</div>
                            <div className="stat-value">{total.toLocaleString()}</div>
                        </div>
                    </div>

                    <div className="table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Year</th>
                                    <th>Attack Type</th>
                                    <th>State</th>
                                    <th>Complaints</th>
                                    <th>Total Loss</th>
                                    <th>Avg Loss/Incident</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.map((item) => (
                                    <tr key={item.id}>
                                        <td>{item.year}</td>
                                        <td className="attack-type">{item.attack_type}</td>
                                        <td>{item.state}</td>
                                        <td>{item.complaint_count.toLocaleString()}</td>
                                        <td className="loss-amount">
                                            ${(item.loss_amount / 1000000).toFixed(2)}M
                                        </td>
                                        <td>
                                            {item.avg_loss_per_incident > 0
                                                ? `$${(item.avg_loss_per_incident).toLocaleString(undefined, {maximumFractionDigits: 0})}`
                                                : (item.loss_amount > 0 && item.complaint_count > 0)
                                                ? `$${(item.loss_amount / item.complaint_count).toLocaleString(undefined, {maximumFractionDigits: 0})}`
                                                : 'N/A'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="pagination-controls">
                        <button
                            disabled={page === 1}
                            onClick={() => fetchData(page - 1, debouncedSearch, attackType, state, year)}
                        >
                            &larr; Previous
                        </button>
                        <span>Page {page} of {totalPages}</span>
                        <button
                            disabled={page >= totalPages}
                            onClick={() => fetchData(page + 1, debouncedSearch, attackType, state, year)}
                        >
                            Next &rarr;
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default IC3Table;
