import React, { Suspense, lazy } from 'react';
import { NavLink, Navigate, useParams } from 'react-router-dom';
import { API_BASE_URL } from '../../api/fetchWithAuth';
import WidgetSkeleton from '../shared/WidgetSkeleton';

const IC3Table = lazy(() => import('./IC3Table'));
const EconomicsTable = lazy(() => import('./EconomicsTable'));

type Dataset = 'ic3' | 'economics';

const DATASETS: { id: Dataset; label: string; description: string }[] = [
  { id: 'ic3',      label: 'IC3 Incidents',  description: 'FBI Internet Crime Complaint Center data' },
  { id: 'economics', label: 'Economics',       description: 'SMB economic indicators by state' },
];

const DataSourcesTab: React.FC = () => {
  const { dataset } = useParams<{ dataset: string }>();

  if (dataset === 'cisa') return <Navigate to="/intel/vulnerabilities?source=kev" replace />;
  if (dataset === 'nvd') return <Navigate to="/intel/vulnerabilities?source=nvd" replace />;

  const current = DATASETS.find(d => d.id === dataset);
  if (!current) return <Navigate to="/intel/reference/ic3" replace />;

  return (
    <div className="tab-page">
      {/* Dataset navigation */}
      <nav
        aria-label="Reference datasets"
        style={{
          display: 'flex',
          gap: 4,
          borderBottom: '1px solid var(--border, #334155)',
          marginBottom: 20,
          overflowX: 'auto',
        }}
      >
        {DATASETS.map(tab => {
          const isActive = tab.id === current.id;
          return (
            <NavLink
              key={tab.id}
              to={`/intel/reference/${tab.id}`}
              style={{
                borderBottom: isActive ? '2px solid var(--accent, #3b82f6)' : '2px solid transparent',
                color: isActive ? 'var(--accent, #3b82f6)' : 'var(--text-secondary, #555)',
                fontWeight: isActive ? 700 : 500,
                fontSize: 13,
                padding: '8px 16px',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                textDecoration: 'none',
                marginBottom: -1,
                transition: 'color 0.15s, border-color 0.15s',
              }}
            >
              {tab.label}
            </NavLink>
          );
        })}
      </nav>

      {/* Dataset description */}
      <p style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', marginBottom: 16 }}>
        {current.description}
      </p>

      {/* Content */}
      <Suspense fallback={<WidgetSkeleton />}>
        {current.id === 'ic3'       && <IC3Table      apiBaseUrl={API_BASE_URL} />}
        {current.id === 'economics' && <EconomicsTable apiBaseUrl={API_BASE_URL} />}
      </Suspense>
    </div>
  );
};

export default DataSourcesTab;
