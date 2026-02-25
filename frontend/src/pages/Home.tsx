import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { checkHealth, HealthResponse } from '../api/health'

const Home = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        setLoading(true)
        const data = await checkHealth()
        setHealth(data)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        setHealth(null)
      } finally {
        setLoading(false)
      }
    }

    fetchHealth()
  }, [])

  return (
    <div>
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '1rem' }}>
        <h1>🛡️ Cyber Threat Intelligence Platform</h1>
        <p style={{ fontSize: '0.95rem', color: '#94a3b8', marginTop: '0.5rem' }}>
          Aggregating, analyzing, and detecting cyber threats
        </p>
      </header>

      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem 1rem' }}>
        <section style={{ marginBottom: '2rem' }}>
          <Link
            to="/dashboard"
            style={{
              display: 'inline-block',
              background: '#1e3a5f',
              color: '#93c5fd',
              border: '1px solid #1e40af',
              borderRadius: '0.375rem',
              padding: '0.5rem 1.25rem',
              textDecoration: 'none',
              fontWeight: 600,
              fontSize: '0.9rem',
            }}
          >
            View Exploited Vulnerabilities →
          </Link>
        </section>

        <section style={{ marginBottom: '2rem' }}>
          <h2>Welcome</h2>
          <p>
            This platform integrates data from multiple threat intelligence sources (CISA KEV, NVD,
            Shodan, etc.) to provide real-time anomaly detection and threat analysis.
          </p>
        </section>

        <section style={{ marginBottom: '2rem' }}>
          <h3>Backend Status</h3>
          {loading && <p style={{ color: '#60a5fa' }}>🔄 Checking backend connection...</p>}
          {error && <p style={{ color: '#fca5a5' }}>❌ Error: {error}</p>}
          {health && (
            <div
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                padding: '1.5rem',
                borderRadius: '0.5rem',
              }}
            >
              <p>
                <strong>Status:</strong> ✅ {health.status}
              </p>
              <p>
                <strong>Service:</strong> {health.service}
              </p>
              <p>
                <strong>Version:</strong> {health.version}
              </p>
              <p>
                <strong>Environment:</strong> {health.environment}
              </p>
            </div>
          )}
        </section>

        <section style={{ marginBottom: '2rem' }}>
          <h3>Platform Features</h3>
          <ul style={{ marginLeft: '1.5rem', lineHeight: '1.8' }}>
            <li>Real-time threat intelligence aggregation</li>
            <li>Anomaly detection pipeline</li>
            <li>Multi-source data integration (CISA, NVD, Shodan, etc.)</li>
            <li>Background ingestion jobs</li>
            <li>RESTful API with versioning</li>
            <li>PostgreSQL data persistence</li>
          </ul>
        </section>

        <section style={{ marginBottom: '2rem' }}>
          <h3>Getting Started</h3>
          <p>📖 Check the README for:</p>
          <ul style={{ marginLeft: '1.5rem', lineHeight: '1.8' }}>
            <li>Docker Compose quickstart</li>
            <li>Local development setup</li>
            <li>Adding new integrations</li>
            <li>API documentation</li>
          </ul>
        </section>

        <section>
          <h3>Development</h3>
          <p>
            <strong>API Endpoints:</strong>
          </p>
          <ul style={{ marginLeft: '1.5rem', lineHeight: '1.8' }}>
            <li>
              <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem' }}>
                GET /health
              </code>{' '}
              - Root health check
            </li>
            <li>
              <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem' }}>
                GET /api/v1/health
              </code>{' '}
              - Versioned health check
            </li>
          </ul>
        </section>
      </main>
    </div>
  )
}

export default Home
