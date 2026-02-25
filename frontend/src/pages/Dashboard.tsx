import { useState, useEffect } from 'react'
import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchExploitedVulns,
  ExploitedVulnItem,
  ExploitedVulnListResponse,
  SeverityLabel,
  SortBy,
  SortOrder,
} from '../api/vulnerabilities'

// ─── Constants ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 25

// ─── Severity badge ───────────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<SeverityLabel, CSSProperties> = {
  Critical: { background: '#450a0a', color: '#fca5a5', border: '1px solid #7f1d1d' },
  High:     { background: '#431407', color: '#fed7aa', border: '1px solid #7c2d12' },
  Medium:   { background: '#422006', color: '#fef08a', border: '1px solid #713f12' },
  Low:      { background: '#172554', color: '#93c5fd', border: '1px solid #1e3a8a' },
  Unknown:  { background: '#1f2937', color: '#9ca3af', border: '1px solid #374151' },
}

function SeverityBadge({
  label,
  score,
}: {
  label: SeverityLabel
  score: number | null
}) {
  return (
    <span
      style={{
        ...SEVERITY_STYLES[label],
        padding: '0.15rem 0.5rem',
        borderRadius: '0.25rem',
        fontSize: '0.78rem',
        fontWeight: 600,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
      {score !== null ? ` (${score.toFixed(1)})` : ''}
    </span>
  )
}

// ─── Sortable column header ───────────────────────────────────────────────────

// Maps a UI column key to the backend sort_by field name.
const COL_TO_SORT_BY: Record<string, SortBy> = {
  id: 'id',
  severity: 'severity_score',
  kev_date: 'kev_date_added',
  nvd_published: 'nvd_published',
}

function SortIndicator({ active, order }: { active: boolean; order: SortOrder }) {
  return (
    <span style={{ marginLeft: '0.3rem', color: active ? '#e2e8f0' : '#475569' }}>
      {active ? (order === 'desc' ? '▼' : '▲') : '⇅'}
    </span>
  )
}

interface SortableHeaderProps {
  colKey: string
  label: string
  currentSortBy: SortBy
  currentSortOrder: SortOrder
  onSort: (col: SortBy) => void
}

function SortableHeader({
  colKey,
  label,
  currentSortBy,
  currentSortOrder,
  onSort,
}: SortableHeaderProps) {
  const sortField = COL_TO_SORT_BY[colKey]
  if (!sortField) {
    return <th style={thStyle}>{label}</th>
  }
  const active = currentSortBy === sortField
  return (
    <th
      style={{ ...thStyle, cursor: 'pointer', userSelect: 'none' }}
      onClick={() => onSort(sortField)}
      title={`Sort by ${label}`}
    >
      {label}
      <SortIndicator active={active} order={currentSortOrder} />
    </th>
  )
}

// ─── Table row ────────────────────────────────────────────────────────────────

function VulnRow({ item }: { item: ExploitedVulnItem }) {
  const vendorProduct =
    [item.vendor, item.product].filter(Boolean).join(' / ') || '—'

  return (
    <tr
      style={{ borderBottom: '1px solid #1e293b' }}
      onMouseEnter={(e) =>
        ((e.currentTarget as HTMLTableRowElement).style.background = '#1a2744')
      }
      onMouseLeave={(e) =>
        ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
      }
    >
      {/* CVE ID — links to NVD */}
      <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
        <a
          href={`https://nvd.nist.gov/vuln/detail/${item.id}`}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: '#60a5fa', textDecoration: 'none', fontFamily: 'monospace', fontSize: '0.85rem' }}
        >
          {item.id}
        </a>
      </td>

      {/* Vulnerability name — truncated with full text in title */}
      <td style={{ ...tdStyle, maxWidth: '320px' }}>
        <span
          title={item.vulnerability_name}
          style={{
            display: 'block',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {item.vulnerability_name}
        </span>
      </td>

      {/* Vendor / Product */}
      <td style={{ ...tdStyle, color: '#94a3b8', whiteSpace: 'nowrap' }}>
        {vendorProduct}
      </td>

      {/* Severity badge */}
      <td style={tdStyle}>
        <SeverityBadge label={item.severity_label} score={item.severity_score} />
      </td>

      {/* KEV Date Added */}
      <td style={{ ...tdStyle, whiteSpace: 'nowrap', color: '#94a3b8' }}>
        {item.kev_date_added ?? '—'}
      </td>

      {/* NVD Published */}
      <td style={{ ...tdStyle, whiteSpace: 'nowrap', color: '#94a3b8' }}>
        {item.nvd_published ?? '—'}
      </td>
    </tr>
  )
}

// ─── Shared cell styles ───────────────────────────────────────────────────────

const thStyle: CSSProperties = {
  textAlign: 'left',
  padding: '0.75rem 1rem',
  color: '#64748b',
  fontWeight: 600,
  fontSize: '0.75rem',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  whiteSpace: 'nowrap',
  background: '#0f172a',
}

const tdStyle: CSSProperties = {
  padding: '0.65rem 1rem',
  fontSize: '0.875rem',
  verticalAlign: 'middle',
  color: '#cbd5e1',
}

// ─── Dashboard page ───────────────────────────────────────────────────────────

const Dashboard = () => {
  const [data, setData] = useState<ExploitedVulnListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState<SortBy>('kev_date_added')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')

  useEffect(() => {
    let cancelled = false

    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const result = await fetchExploitedVulns({
          page,
          pageSize: PAGE_SIZE,
          sortBy,
          sortOrder,
        })
        if (!cancelled) setData(result)
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchData()
    return () => {
      cancelled = true
    }
  }, [page, sortBy, sortOrder])

  const handleSort = (col: SortBy) => {
    if (col === sortBy) {
      setSortOrder((o) => (o === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortBy(col)
      setSortOrder('desc')
    }
    setPage(1) // reset to first page on sort change
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div>
      {/* Header */}
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '1rem' }}>
        <h1>🛡️ Exploited Vulnerabilities</h1>
        <p style={{ fontSize: '0.95rem', color: '#94a3b8', marginTop: '0.5rem' }}>
          CISA Known Exploited Vulnerabilities (KEV) catalog
        </p>
      </header>

      <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1rem' }}>
        {/* Nav */}
        <div style={{ marginBottom: '1.25rem' }}>
          <Link
            to="/"
            style={{ color: '#60a5fa', textDecoration: 'none', fontSize: '0.875rem' }}
          >
            ← Back to Home
          </Link>
        </div>

        {/* Status bar */}
        {data && !loading && (
          <p style={{ color: '#64748b', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Showing{' '}
            <strong style={{ color: '#94a3b8' }}>{data.items.length}</strong> of{' '}
            <strong style={{ color: '#94a3b8' }}>{data.total}</strong> exploited
            vulnerabilities
          </p>
        )}

        {/* Loading state */}
        {loading && (
          <div
            style={{
              padding: '3rem',
              textAlign: 'center',
              color: '#60a5fa',
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '0.5rem',
            }}
          >
            🔄 Loading vulnerabilities…
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div
            style={{
              background: '#450a0a',
              border: '1px solid #7f1d1d',
              borderRadius: '0.5rem',
              padding: '1rem 1.5rem',
              color: '#fca5a5',
              marginBottom: '1rem',
            }}
          >
            ❌ {error}
          </div>
        )}

        {/* Table + pagination */}
        {!loading && !error && data && (
          <>
            {data.items.length === 0 ? (
              // Empty state
              <div
                style={{
                  background: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '0.5rem',
                  padding: '3rem',
                  textAlign: 'center',
                  color: '#64748b',
                }}
              >
                No exploited vulnerabilities found.
              </div>
            ) : (
              <div
                style={{
                  background: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '0.5rem',
                  overflowX: 'auto',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <SortableHeader
                        colKey="id"
                        label="CVE ID"
                        currentSortBy={sortBy}
                        currentSortOrder={sortOrder}
                        onSort={handleSort}
                      />
                      <th style={thStyle}>Vulnerability</th>
                      <th style={thStyle}>Vendor / Product</th>
                      <SortableHeader
                        colKey="severity"
                        label="Severity"
                        currentSortBy={sortBy}
                        currentSortOrder={sortOrder}
                        onSort={handleSort}
                      />
                      <SortableHeader
                        colKey="kev_date"
                        label="KEV Date Added"
                        currentSortBy={sortBy}
                        currentSortOrder={sortOrder}
                        onSort={handleSort}
                      />
                      <SortableHeader
                        colKey="nvd_published"
                        label="NVD Published"
                        currentSortBy={sortBy}
                        currentSortOrder={sortOrder}
                        onSort={handleSort}
                      />
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item) => (
                      <VulnRow key={item.id} item={item} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination controls */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginTop: '1rem',
                color: '#64748b',
                fontSize: '0.875rem',
              }}
            >
              <button
                onClick={() => setPage((p) => p - 1)}
                disabled={page <= 1}
                style={{
                  background: page <= 1 ? '#1e293b' : '#1e3a5f',
                  color: page <= 1 ? '#475569' : '#93c5fd',
                  border: '1px solid #334155',
                  borderRadius: '0.375rem',
                  padding: '0.4rem 1rem',
                  cursor: page <= 1 ? 'not-allowed' : 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                ← Prev
              </button>

              <span>
                Page{' '}
                <strong style={{ color: '#94a3b8' }}>{page}</strong> of{' '}
                <strong style={{ color: '#94a3b8' }}>{totalPages}</strong>
                &nbsp;·&nbsp;
                {data.total} total
              </span>

              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
                style={{
                  background: page >= totalPages ? '#1e293b' : '#1e3a5f',
                  color: page >= totalPages ? '#475569' : '#93c5fd',
                  border: '1px solid #334155',
                  borderRadius: '0.375rem',
                  padding: '0.4rem 1rem',
                  cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                  fontSize: '0.875rem',
                }}
              >
                Next →
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default Dashboard
