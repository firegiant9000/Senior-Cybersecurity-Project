import React, { useState, useEffect, useCallback } from 'react';
import { fetchIngestRuns, fetchIngestFreshness, type IngestRunItem, type SourceFreshness } from '../api/ingest';

const PAGE_SIZE = 15;

const SOURCE_LABELS: Record<string, string> = {
    cisa_kev: 'CISA KEV',
    nvd: 'NVD',
    ic3: 'IC3',
    econ: 'Economics',
    economics: 'Economics',
};

const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
    success: { bg: '#dcfce7', color: '#166534' },
    completed: { bg: '#dcfce7', color: '#166534' },
    running: { bg: '#fef9c3', color: '#854d0e' },
    pending: { bg: '#f3f4f6', color: '#374151' },
    failed: { bg: '#fee2e2', color: '#991b1b' },
};

function capitalize(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function fmtDuration(start: string | null, end: string | null): string {
    if (!start || !end) return '—';
    const ms = new Date(end).getTime() - new Date(start).getTime();
    if (ms < 1000) return `${ms}ms`;
    const secs = Math.floor(ms / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    return `${mins}m ${secs % 60}s`;
}

function fmtTime(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
}

const PipelineHealthTab: React.FC = () => {
    const [runs, setRuns] = useState<IngestRunItem[]>([]);
    const [freshness, setFreshness] = useState<SourceFreshness[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [sourceFilter, setSourceFilter] = useState('');

    const fetchData = useCallback(async (p: number, source: string, signal?: AbortSignal) => {
        setLoading(true);
        setError(null);
        try {
            const result = await fetchIngestRuns(
                signal ?? new AbortController().signal,
                p,
                PAGE_SIZE,
                source || undefined,
            );
            setRuns(result.items);
            setTotal(result.total);
            setPage(p);
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            setError(err instanceof Error ? err.message : 'Error fetching pipeline runs');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const controller = new AbortController();
        fetchData(1, sourceFilter, controller.signal);
        fetchIngestFreshness(controller.signal)
            .then(r => setFreshness(r.sources))
            .catch(() => { /* non-fatal */ });
        return () => controller.abort();
    }, [fetchData, sourceFilter]);

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    return (
        <div className="data-table-container">
            <h2>Pipeline Health</h2>

            {/* Summary cards */}
            {freshness.length > 0 && (
                <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
                    {freshness.map(s => {
                        const style = STATUS_STYLES[s.status ?? 'pending'] ?? STATUS_STYLES.pending;
                        return (
                            <div
                                key={s.source}
                                style={{
                                    padding: '14px 20px',
                                    borderRadius: '8px',
                                    background: style.bg,
                                    color: style.color,
                                    minWidth: '180px',
                                    flex: '1 1 180px',
                                }}
                            >
                                <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: '4px' }}>
                                    {SOURCE_LABELS[s.source] ?? s.source}
                                </div>
                                <div style={{ fontSize: '12px' }}>
                                    Status: <strong>{capitalize(s.status ?? 'unknown')}</strong>
                                </div>
                                <div style={{ fontSize: '12px' }}>
                                    Total Records: {s.total_records?.toLocaleString() ?? '—'}
                                </div>
                                <div style={{ fontSize: '12px' }}>
                                    Last Run New: {s.records_ingested?.toLocaleString() ?? '—'}
                                </div>
                                <div style={{ fontSize: '12px' }}>
                                    Last run: {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : 'never'}
                                </div>
                                {s.error_message && (
                                    <div style={{ fontSize: '11px', marginTop: '4px', color: '#991b1b' }}>
                                        Error: {s.error_message.substring(0, 100)}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Filters */}
            <div className="filter-controls">
                <div className="filter-group">
                    <label htmlFor="pipeline-source">Source</label>
                    <select
                        id="pipeline-source"
                        value={sourceFilter}
                        onChange={(e) => setSourceFilter(e.target.value)}
                    >
                        <option value="">All</option>
                        <option value="nvd">NVD</option>
                        <option value="cisa_kev">CISA KEV</option>
                        <option value="ic3">IC3</option>
                        <option value="economics">Economics</option>
                    </select>
                </div>
                <button
                    className="reset-filters-btn"
                    onClick={() => setSourceFilter('')}
                >
                    Reset Filters
                </button>
            </div>

            <div className="pagination-info">Showing {runs.length} of {total} runs</div>
            {loading && <p>Loading pipeline runs...</p>}
            {error && <p className="error">Error: {error}</p>}

            {!loading && !error && runs.length === 0 && (
                <div className="empty-state">
                    <p>No pipeline runs found. Data ingestion has not been run yet.</p>
                </div>
            )}

            {runs.length > 0 && (
                <>
                    <div className="table-scroll-wrapper">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Source</th>
                                    <th>Status</th>
                                    <th>Started</th>
                                    <th>Duration</th>
                                    <th>New Records</th>
                                    <th>Total Records</th>
                                    <th>Error</th>
                                </tr>
                            </thead>
                            <tbody>
                                {runs.map((run) => {
                                    const style = STATUS_STYLES[run.status] ?? STATUS_STYLES.pending;
                                    return (
                                        <tr key={run.id}>
                                            <td style={{ fontWeight: 600 }}>
                                                {SOURCE_LABELS[run.source] ?? run.source}
                                            </td>
                                            <td>
                                                <span style={{
                                                    padding: '3px 10px',
                                                    borderRadius: '12px',
                                                    fontSize: '12px',
                                                    fontWeight: 600,
                                                    background: style.bg,
                                                    color: style.color,
                                                }}>
                                                    {capitalize(run.status)}
                                                </span>
                                            </td>
                                            <td>{fmtTime(run.started_at)}</td>
                                            <td>{fmtDuration(run.started_at, run.finished_at)}</td>
                                            <td>{run.records_ingested.toLocaleString()}</td>
                                            <td>{freshness.find(f => f.source === run.source)?.total_records?.toLocaleString() ?? '—'}</td>
                                            <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                {run.error_message || '—'}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <div className="pagination-controls">
                        <button disabled={page === 1} onClick={() => fetchData(page - 1, sourceFilter)}>
                            &larr; Previous
                        </button>
                        <span>Page {page} of {totalPages}</span>
                        <button disabled={page >= totalPages} onClick={() => fetchData(page + 1, sourceFilter)}>
                            Next &rarr;
                        </button>
                    </div>
                </>
            )}
        </div>
    );
};

export default PipelineHealthTab;
