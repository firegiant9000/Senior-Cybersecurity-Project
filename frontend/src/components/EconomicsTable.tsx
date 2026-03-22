import React, { useState, useEffect, useCallback } from 'react';
import { useDebounce } from '../hooks/useDebounce';

interface EconomicsItem {
    id: number;
    state: string;
    smb_count: number;
    avg_revenue: number;
}

interface ApiResponse {
    total: number;
    page: number;
    page_size: number;
    items: EconomicsItem[];
}

const PAGE_SIZE = 10;

const formatCurrencyCompact = (value: number): string => {
    const abs = Math.abs(value);
    if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `$${(value / 1e3).toFixed(2)}K`;
    return `$${value.toFixed(2)}`;
};

interface Props {
    apiBaseUrl: string;
}

type SortField = 'state' | 'smb_count' | 'avg_revenue';
type SortOrder = 'asc' | 'desc';

const EconomicsTable: React.FC<Props> = ({ apiBaseUrl }) => {
    const [data, setData] = useState<EconomicsItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);

    // Filter state
    const [searchInput, setSearchInput] = useState('');
    const debouncedSearch = useDebounce(searchInput);

    // Sort state
    const [sortBy, setSortBy] = useState<SortField>('smb_count');
    const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

    const handleSort = (field: SortField) => {
        if (sortBy === field) {
            setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
        } else {
            setSortBy(field);
            setSortOrder('desc');
        }
    };

    const fetchData = useCallback(async (p: number, search: string, sb: SortField, so: SortOrder, signal?: AbortSignal) => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                page: String(p),
                page_size: String(PAGE_SIZE),
                sort_by: sb,
                sort_order: so,
            });
            if (search) params.set('search', search);

            const response = await fetch(`${apiBaseUrl}/api/v1/economics/indicators?${params}`, signal ? { signal } : undefined);
            if (!response.ok) throw new Error(`Failed to fetch economics data: ${response.status}`);
            const result: ApiResponse = await response.json();
            setData(result.items);
            setTotal(result.total);
            setPage(p);
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            const errorMsg = err instanceof Error ? err.message : 'Error fetching data';
            console.error('Economics fetch error:', errorMsg);
            setError(errorMsg);
        } finally {
            setLoading(false);
        }
    }, [apiBaseUrl]);

    // Reset to page 1 when filters or sort change
    useEffect(() => {
        const controller = new AbortController();
        fetchData(1, debouncedSearch, sortBy, sortOrder, controller.signal);
        return () => controller.abort();
    }, [debouncedSearch, sortBy, sortOrder, fetchData]);

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    return (
        <div className="data-table-container">
            <h2>State Economic Indicators</h2>

            <div className="filter-controls">
                <div className="filter-group">
                    <label htmlFor="econ-search">Search State</label>
                    <input
                        id="econ-search"
                        type="text"
                        placeholder="e.g. CA"
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                    />
                </div>
                <button
                    className="reset-filters-btn"
                    onClick={() => { setSearchInput(''); setSortBy('smb_count'); setSortOrder('desc'); }}
                >
                    Reset Filters
                </button>
            </div>

            <div className="pagination-info">Showing {data.length} of {total} states</div>
            {loading && <p>Loading economics data...</p>}
            {error && <p className="error">Error: {error}</p>}

            {!loading && !error && data.length === 0 && (
                <div className="empty-state">
                    <p>No states found matching your search.</p>
                </div>
            )}

            {data.length > 0 && (
                <>
                    <div className="table-scroll-wrapper">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th className="sortable-th" aria-sort={sortBy === 'state' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                    <button type="button" onClick={() => handleSort('state')}>
                                        State {sortBy === 'state' ? (sortOrder === 'asc' ? '▲' : '▼') : ''}
                                    </button>
                                </th>
                                <th className="sortable-th" aria-sort={sortBy === 'smb_count' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                    <button type="button" onClick={() => handleSort('smb_count')}>
                                        Small Business Count {sortBy === 'smb_count' ? (sortOrder === 'asc' ? '▲' : '▼') : ''}
                                    </button>
                                </th>
                                <th className="sortable-th" aria-sort={sortBy === 'avg_revenue' ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'}>
                                    <button type="button" onClick={() => handleSort('avg_revenue')}>
                                        Average Revenue {sortBy === 'avg_revenue' ? (sortOrder === 'asc' ? '▲' : '▼') : ''}
                                    </button>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((item) => (
                                <tr key={item.id}>
                                    <td>{item.state}</td>
                                    <td>{item.smb_count.toLocaleString()}</td>
                                    <td>{formatCurrencyCompact(item.avg_revenue)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    </div>
                    <div className="pagination-controls">
                        <button disabled={page === 1} onClick={() => fetchData(page - 1, debouncedSearch, sortBy, sortOrder)}>
                            &larr; Previous
                        </button>
                        <span>Page {page} of {totalPages}</span>
                        <button disabled={page >= totalPages} onClick={() => fetchData(page + 1, debouncedSearch, sortBy, sortOrder)}>
                            Next &rarr;
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default EconomicsTable;
