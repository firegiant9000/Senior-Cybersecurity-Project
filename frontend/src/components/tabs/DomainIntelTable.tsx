import React, { useState, useEffect, useCallback } from 'react';
import { fetchFindingsHistory, type SnapshotListItem } from '../../api/findings';
import { useAuth } from '../../context/AuthContext';
import SeverityBadge from '../shared/SeverityBadge';

/**
 * All domain intelligence sources the findings engine can use.
 * "requiresKey" sources are skipped when the API key isn't configured.
 */
const ALL_SOURCES: {
  id: string;
  label: string;
  tier: string;
  requiresKey: boolean;
  description: string;
}[] = [
  { id: 'ic3_sector_weights', label: 'IC3 Sector Weights', tier: 'Always', requiresKey: false, description: 'FBI IC3 attack-type distribution per industry sector' },
  { id: 'kev_vendor_match', label: 'CISA KEV Vendor Match', tier: 'Always', requiresKey: false, description: 'Known exploited CVEs matched to your vendor stack' },
  { id: 'assessment_readiness', label: 'Assessment Readiness', tier: 'Always', requiresKey: false, description: 'Profile completeness scoring and data gap analysis' },
  { id: 'mitre_attack', label: 'MITRE ATT&CK Enrichment', tier: 'Always', requiresKey: false, description: 'Technique IDs and mitigations mapped from IC3 attack types' },
  { id: 'security_controls', label: 'Security Controls', tier: 'Always', requiresKey: false, description: 'CIS IG1 baseline scoring from your security checklist' },
  { id: 'compliance_frameworks', label: 'Compliance Frameworks', tier: 'Always', requiresKey: false, description: 'Industry and data-type compliance gap detection' },
  { id: 'dns_checks', label: 'DNS (SPF/DMARC/DKIM)', tier: 'Tier 1', requiresKey: false, description: 'Email authentication record presence checks' },
  { id: 'http_header_checks', label: 'HTTP Security Headers', tier: 'Tier 1', requiresKey: false, description: 'HSTS, CSP, X-Frame-Options, and more' },
  { id: 'ssl_checks', label: 'SSL/TLS Certificate', tier: 'Tier 1', requiresKey: false, description: 'Certificate expiry, self-signed detection, TLS version' },
  { id: 'tech_fingerprint', label: 'Tech Fingerprinting', tier: 'Tier 1', requiresKey: false, description: 'CMS, web server, framework, and CDN detection' },
  { id: 'crtsh', label: 'crt.sh CT Logs', tier: 'Tier 2', requiresKey: false, description: 'Certificate Transparency subdomain enumeration' },
  { id: 'hibp', label: 'HIBP Domain Breaches', tier: 'Tier 2', requiresKey: true, description: 'Have I Been Pwned account breach search' },
  { id: 'shodan', label: 'Shodan Host Lookup', tier: 'Tier 2', requiresKey: true, description: 'Open ports, internet-exposed services, and CVEs' },
  { id: 'otx', label: 'AlienVault OTX', tier: 'Tier 2', requiresKey: true, description: 'Crowd-sourced threat intelligence pulse data' },
];

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

interface Props {
  onNavigateToFindings?: () => void;
}

const DomainIntelTable: React.FC<Props> = ({ onNavigateToFindings }) => {
  const { user } = useAuth();
  const [snapshot, setSnapshot] = useState<SnapshotListItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [noData, setNoData] = useState(false);

  const load = useCallback(() => {
    if (!user) return;
    const controller = new AbortController();
    setLoading(true);
    fetchFindingsHistory(controller.signal, 1)
      .then((resp) => {
        if (resp.items.length > 0) {
          setSnapshot(resp.items[0]);
        } else {
          setNoData(true);
        }
      })
      .catch(() => setNoData(true))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user]);

  useEffect(() => {
    const cleanup = load();
    return cleanup;
  }, [load]);

  if (loading) {
    return <p style={{ color: 'var(--text-muted, #64748b)', fontSize: 13 }}>Loading source status...</p>;
  }

  if (noData || !snapshot) {
    return (
      <div style={{ textAlign: 'center', padding: '32px 16px' }}>
        <p style={{ color: 'var(--text-secondary, #555)', marginBottom: 12 }}>
          No scan data yet. Run a findings scan to see which intelligence sources are active.
        </p>
        {onNavigateToFindings && (
          <button
            onClick={onNavigateToFindings}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--accent, #3b82f6)',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
              textDecoration: 'underline',
            }}
          >
            Go to Findings tab
          </button>
        )}
      </div>
    );
  }

  const activeSet = new Set(snapshot.data_sources_used);
  const scanDate = new Date(snapshot.generated_at).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
  });

  return (
    <div>
      <p style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', marginBottom: 12 }}>
        Status from most recent scan: {scanDate} &middot; Tier: {capitalize(snapshot.assessment_tier)}
      </p>

      {/* Summary counters */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 13, color: 'var(--text-secondary, #555)' }}>
          <strong>{activeSet.size}</strong> / {ALL_SOURCES.length} sources active
        </div>
        {snapshot.summary.by_severity.critical != null && snapshot.summary.by_severity.critical > 0 && (
          <span style={{ fontSize: 13 }}>
            <SeverityBadge label="Critical" /> {snapshot.summary.by_severity.critical}
          </span>
        )}
        {snapshot.summary.by_severity.high != null && snapshot.summary.by_severity.high > 0 && (
          <span style={{ fontSize: 13 }}>
            <SeverityBadge label="High" /> {snapshot.summary.by_severity.high}
          </span>
        )}
        <span style={{ fontSize: 13, color: 'var(--text-muted, #64748b)' }}>
          {snapshot.summary.total} total findings
        </span>
      </div>

      {/* Sources table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border, #334155)' }}>
            <th style={thStyle}>Source</th>
            <th style={thStyle}>Tier</th>
            <th style={thStyle}>Status</th>
            <th style={{ ...thStyle, minWidth: 200 }}>Description</th>
          </tr>
        </thead>
        <tbody>
          {ALL_SOURCES.map((src) => {
            const active = activeSet.has(src.id);
            let status: string;
            let statusColor: string;
            if (active) {
              status = 'Active';
              statusColor = 'var(--success, #16a34a)';
            } else if (src.requiresKey) {
              status = 'Needs API Key';
              statusColor = 'var(--text-muted, #9ca3af)';
            } else {
              status = 'No Data';
              statusColor = 'var(--text-muted, #9ca3af)';
            }
            return (
              <tr key={src.id} style={{ borderBottom: '1px solid var(--border, #1e293b)' }}>
                <td style={tdStyle}>
                  <span style={{ fontWeight: 600 }}>{src.label}</span>
                </td>
                <td style={tdStyle}>
                  <span style={{
                    fontSize: 11,
                    padding: '2px 8px',
                    borderRadius: 8,
                    background: src.tier === 'Always' ? 'var(--accent-bg, #eef2ff)' : 'var(--bg-secondary, #f0f1f5)',
                    color: src.tier === 'Always' ? 'var(--accent, #3b82f6)' : 'var(--text-muted, #64748b)',
                    fontWeight: 600,
                  }}>
                    {src.tier}
                  </span>
                </td>
                <td style={tdStyle}>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    color: statusColor,
                    fontWeight: 500,
                  }}>
                    <span style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: statusColor,
                      display: 'inline-block',
                    }} />
                    {status}
                  </span>
                </td>
                <td style={{ ...tdStyle, color: 'var(--text-muted, #64748b)' }}>
                  {src.description}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 10px',
  fontSize: 11,
  fontWeight: 700,
  color: 'var(--text-muted, #64748b)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const tdStyle: React.CSSProperties = {
  padding: '10px 10px',
  verticalAlign: 'middle',
};

export default DomainIntelTable;
