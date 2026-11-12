import { useSearchParams } from 'react-router-dom';
import { API_BASE_URL } from '../../api/fetchWithAuth';
import RiskScoringTable from '../tabs/RiskScoringTable';
import CisaKevTable from '../tabs/CisaKevTable';
import NvdTable from '../tabs/NvdTable';
import VulnerabilitySummary from './VulnerabilitySummary';
import { parseVulnSource, type VulnSource } from './vulnSource';

const SOURCES: { key: VulnSource; label: string }[] = [
  { key: 'scored', label: 'Risk-scored' },
  { key: 'kev', label: 'CISA KEV' },
  { key: 'nvd', label: 'NVD' },
];

export default function VulnerabilitiesScreen() {
  const [searchParams, setSearchParams] = useSearchParams();
  const source = parseVulnSource(searchParams.get('source'));

  const selectSource = (s: VulnSource) => {
    setSearchParams((p) => {
      p.set('source', s);
      return p;
    });
  };

  return (
    <div className="vulnerabilities-screen">
      <h2>Vulnerabilities</h2>
      <VulnerabilitySummary />
      <div role="tablist" aria-label="Vulnerability source" className="tab-bar">
        {SOURCES.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={source === key}
            className={source === key ? 'tab-btn active' : 'tab-btn'}
            onClick={() => selectSource(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {source === 'scored' && <RiskScoringTable apiBaseUrl={API_BASE_URL} showSummary={false} />}
      {source === 'kev' && <CisaKevTable apiBaseUrl={API_BASE_URL} />}
      {source === 'nvd' && <NvdTable apiBaseUrl={API_BASE_URL} />}
    </div>
  );
}
