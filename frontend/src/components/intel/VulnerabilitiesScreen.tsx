import type { KeyboardEvent } from 'react';
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

  const onTabKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const current = SOURCES.findIndex((s) => s.key === source);
    let next: number;
    switch (e.key) {
      case 'ArrowRight':
        next = (current + 1) % SOURCES.length;
        break;
      case 'ArrowLeft':
        next = (current - 1 + SOURCES.length) % SOURCES.length;
        break;
      case 'Home':
        next = 0;
        break;
      case 'End':
        next = SOURCES.length - 1;
        break;
      default:
        return;
    }
    e.preventDefault();
    selectSource(SOURCES[next].key);
    document.getElementById(`vuln-tab-${SOURCES[next].key}`)?.focus();
  };

  return (
    <div className="vulnerabilities-screen">
      <h2>Vulnerabilities</h2>
      <VulnerabilitySummary />
      <div
        role="tablist"
        aria-label="Vulnerability source"
        className="tab-bar"
        onKeyDown={onTabKeyDown}
      >
        {SOURCES.map(({ key, label }) => (
          <button
            key={key}
            id={`vuln-tab-${key}`}
            type="button"
            role="tab"
            aria-selected={source === key}
            aria-controls="vuln-panel"
            tabIndex={source === key ? 0 : -1}
            className={source === key ? 'tab-btn active' : 'tab-btn'}
            onClick={() => selectSource(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="vuln-panel" aria-labelledby={`vuln-tab-${source}`} tabIndex={0}>
        {source === 'scored' && <RiskScoringTable apiBaseUrl={API_BASE_URL} showSummary={false} />}
        {source === 'kev' && <CisaKevTable apiBaseUrl={API_BASE_URL} />}
        {source === 'nvd' && <NvdTable apiBaseUrl={API_BASE_URL} />}
      </div>
    </div>
  );
}
