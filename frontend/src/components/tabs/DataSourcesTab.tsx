import React, { useState, Suspense, lazy } from 'react';
import { API_BASE_URL } from '../../api/fetchWithAuth';
import WidgetSkeleton from '../shared/WidgetSkeleton';

const IC3Table = lazy(() => import('./IC3Table'));
const EconomicsTable = lazy(() => import('./EconomicsTable'));
const CisaKevTable = lazy(() => import('./CisaKevTable'));
const NvdTable = lazy(() => import('./NvdTable'));

type SubTab = 'ic3' | 'economics' | 'cisa' | 'nvd';

const SUB_TABS: { id: SubTab; label: string; description: string }[] = [
  { id: 'ic3',       label: 'IC3 Incidents',  description: 'FBI Internet Crime Complaint Center data' },
  { id: 'economics', label: 'Economics',       description: 'SMB economic indicators by state' },
  { id: 'cisa',      label: 'CISA KEV',        description: 'Known Exploited Vulnerabilities catalog' },
  { id: 'nvd',       label: 'NVD CVEs',        description: 'National Vulnerability Database' },
];

const DataSourcesTab: React.FC = () => {
  const [active, setActive] = useState<SubTab>('ic3');
  const current = SUB_TABS.find(t => t.id === active)!;

  return (
    <div className="tab-page">
      {/* Sub-tab bar */}
      <div style={{
        display: 'flex',
        gap: 4,
        borderBottom: '1px solid var(--border, #334155)',
        marginBottom: 20,
        overflowX: 'auto',
      }}>
        {SUB_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            style={{
              background: 'transparent',
              border: 'none',
              borderBottom: active === tab.id ? '2px solid var(--accent, #3b82f6)' : '2px solid transparent',
              color: active === tab.id ? 'var(--accent, #3b82f6)' : 'var(--text-secondary, #94a3b8)',
              fontWeight: active === tab.id ? 700 : 500,
              fontSize: 13,
              padding: '8px 16px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              marginBottom: -1,
              transition: 'color 0.15s, border-color 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sub-tab description */}
      <p style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', marginBottom: 16 }}>
        {current.description}
      </p>

      {/* Content */}
      <Suspense fallback={<WidgetSkeleton />}>
        {active === 'ic3'       && <IC3Table       apiBaseUrl={API_BASE_URL} />}
        {active === 'economics' && <EconomicsTable  apiBaseUrl={API_BASE_URL} />}
        {active === 'cisa'      && <CisaKevTable    apiBaseUrl={API_BASE_URL} />}
        {active === 'nvd'       && <NvdTable        apiBaseUrl={API_BASE_URL} />}
      </Suspense>
    </div>
  );
};

export default DataSourcesTab;
