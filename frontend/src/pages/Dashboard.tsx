import Dashboard from '../Dashboard'

export default Dashboard

/*

interface TabButtonProps {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}

function TabButton({ active, onClick, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '0.75rem 1.5rem',
        border: 'none',
        background: active ? '#1e293b' : 'transparent',
        color: active ? '#e2e8f0' : '#64748b',
        cursor: 'pointer',
        borderBottom: active ? '2px solid #60a5fa' : '1px solid #334155',
        fontSize: '0.875rem',
        fontWeight: active ? 600 : 400,
        transition: 'all 0.2s',
      }}
    >
      {children}
    </button>
  )
}

// ─── CISA KEV Components ──────────────────────────────────────────────────────

function CisaKevView() {
  const [data, setData] = useState<ExploitedVulnListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState<VulnSortBy>('kev_date_added')
  const [sortOrder, setSortOrder] = useState<VulnSortOrder>('desc')

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

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  if (loading) return <LoadingState />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  return (
    <div>
      {data && !loading && (
        <p style={{ color: '#64748b', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Showing <strong style={{ color: '#94a3b8' }}>{data.items.length}</strong> of{' '}
          <strong style={{ color: '#94a3b8' }}>{data.total}</strong> exploited vulnerabilities
        </p>
      )}

      {data.items.length === 0 ? (
        <EmptyState message="No exploited vulnerabilities found." />
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
                <th style={thStyle}>CVE ID</th>
                <th style={thStyle}>Vulnerability</th>
                <th style={thStyle}>Vendor / Product</th>
                <th style={thStyle}>Severity</th>
                <th style={thStyle}>KEV Date Added</th>
                <th style={thStyle}>NVD Published</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id} style={{ borderBottom: '1px solid #1e293b' }}>
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
                  <td style={{ ...tdStyle, maxWidth: '320px' }}>
                    <span title={item.vulnerability_name} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                      {item.vulnerability_name}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, color: '#94a3b8', whiteSpace: 'nowrap' }}>
                    {[item.vendor, item.product].filter(Boolean).join(' / ') || '—'}
                  </td>
                  <td style={tdStyle}>
                    <SeverityBadge label={item.severity_label} score={item.severity_score} />
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap', color: '#94a3b8' }}>
                    {item.kev_date_added ?? '—'}
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap', color: '#94a3b8' }}>
                    {item.nvd_published ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
       Main Dashboard Component ─────────────────────────────────────────────────

const Dashboard = () => {
  const [activeTab, setActiveTab] = useState<TabType>('cisa-kev')

  return (
    <div>
      {/* Header * /}
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '1rem' }}>
        <h1>🛡️ Cyber Threat Intelligence Dashboard</h1>
        <p style={{ fontSize: '0.95rem', color: '#94a3b8', marginTop: '0.5rem' }}>
          Aggregated data from CISA, NVD, IC3, and economic indicators
        </p>
      </header>

      <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1rem' }}>
        {/* Nav * /}
        <div style={{ marginBottom: '1.25rem' }}>
          <Link
            to="/"
            style={{ color: '#60a5fa', textDecoration: 'none', fontSize: '0.875rem' }}
          >
            ← Back to Home
          </Link>
        </div>

        {/* Tabs * /}
        <div style={{ borderBottom: '1px solid #334155', marginBottom: '1.5rem', display: 'flex' }}>
          <TabButton
            active={activeTab === 'cisa-kev'}
            onClick={() => setActiveTab('cisa-kev')}
          >
            📋 CISA KEV
          </TabButton>
          <TabButton
            active={activeTab === 'nvd'}
            onClick={() => setActiveTab('nvd')}
          >
            🔍 NVD CVEs
          </TabButton>
          <TabButton
            active={activeTab === 'ic3'}
            onClick={() => setActiveTab('ic3')}
          >
            🚨 IC3 Incidents
          </TabButton>
          <TabButton
            active={activeTab === 'economics'}
            onClick={() => setActiveTab('economics')}
          >
            💼 Economics
          </TabButton>
        </div>

        {/* Tab content * /}
        {activeTab === 'cisa-kev' && <CisaKevView />}
        {activeTab === 'nvd' && <NvdView />}
        {activeTab === 'ic3' && <IC3View />}
        {activeTab === 'economics' && <EconomicsView />f (!cancelled)
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

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  if (loading) return <LoadingState />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  return (
    <div>
      <p style={{ color: '#64748b', fontSize: '0.875rem', marginBottom: '1rem' }}>
        Showing <strong style={{ color: '#94a3b8' }}>{data.items.length}</strong> of{' '}
        <strong style={{ color: '#94a3b8' }}>{data.total}</strong> economic indicators
      </p>

      {data.items.length === 0 ? (
        <EmptyState message="No economic indicators found." />
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
                <th style={thStyle}>State</th>
                <th style={thStyle}>Median Income</th>
                <th style={thStyle}>Unemployment Rate (%)</th>
                <th style={thStyle}>Poverty Rate (%)</th>
                <th style={thStyle}>Population</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>{item.state}</td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                    {item.median_income !== null ? `$${item.median_income.toLocaleString()}` : '—'}
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                    {item.unemployment_rate !== null ? item.unemployment_rate.toFixed(2) : '—'}
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                    {item.poverty_rate !== null ? item.poverty_rate.toFixed(2) : '—'}
                  </td>
                  <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                    {item.population !== null ? item.population.toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Pagination page={page} totalPages={totalPages} total={data.total} onPageChange={setPage} />
    </div>
  )
}

// ─── Shared components ────────────────────────────────────────────────────────

function LoadingState() {
  return (
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
      🔄 Loading…
    </div>
  )
}

function ErrorState({ error }: { error: string }) {
  return (
    <div
      style={{
        background: '#450a0a',
        border: '1px solid #7f1d1d',
        borderRadius: '0.5rem',
        padding: '1rem 1.5rem',
        color: '#fca5a5',
      }}
    >
      ❌ {error}
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
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
      {message}
    </div>
  )
}

interface PaginationProps {
  page: number
  totalPages: number
  total: number
  onPageChange: (page: number) => void
}

function Pagination({ page, totalPages, total, onPageChange }: PaginationProps) {
  return (
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
        onClick={() => onPageChange(page - 1)}
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
        Page <strong style={{ color: '#94a3b8' }}>{page}</strong> of{' '}
        <strong style={{ color: '#94a3b8' }}>{totalPages}</strong>
        &nbsp;·&nbsp;
        {total} total
      </span>

      <button
        onClick={() => onPageChange(page + 1)}
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
      {/* Header * /}
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '1rem' }}>
        <h1>🛡️ Exploited Vulnerabilities</h1>
        <p style={{ fontSize: '0.95rem', color: '#94a3b8', marginTop: '0.5rem' }}>
          CISA Known Exploited Vulnerabilities (KEV) catalog
        </p>
      </header>

      <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem 1rem' }}>
        {/* Nav * /}
        <div style={{ marginBottom: '1.25rem' }}>
          <Link
            to="/"
            style={{ color: '#60a5fa', textDecoration: 'none', fontSize: '0.875rem' }}
          >
            ← Back to Home
          </Link>
        </div>

        {/* Status bar * /}
        {data && !loading && (
          <p style={{ color: '#64748b', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Showing{' '}
            <strong style={{ color: '#94a3b8' }}>{data.items.length}</strong> of{' '}
            <strong style={{ color: '#94a3b8' }}>{data.total}</strong> exploited
            vulnerabilities
          </p>
        )}

        {/* Loading state * /}
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

        {/* Error state * /}
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

        {/* Table + pagination * /}
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

            {/* Pagination controls * /}
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

*/
