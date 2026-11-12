import React from 'react';
import { useIncidentLandscape } from '../../hooks/useIncidentLandscape';
import SourceBadge from '../shared/SourceBadge';
import CyberSecurityMap from '../charts/CyberSecurityMap';
import SectorAttackHeatmap from '../charts/SectorAttackHeatmap';
import SectorImpactTable from '../charts/SectorImpactTable';
import LossByAttackTypeChart from '../charts/LossByAttackTypeChart';
import MalwareBarChart from '../charts/MalwareBarChart';

const IncidentLandscape: React.FC = () => {
  const { geographicThreats, sectorAttackMatrix, industryRisk, attackTypes, loading, errors } =
    useIncidentLandscape();

  return (
    <section className="incident-landscape" style={{ marginTop: 24 }}>
      <h3>Incident landscape</h3>
      {errors.map(message => (
        <p key={message} role="alert" style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>
          {message}
        </p>
      ))}
      <div className="incident-landscape-widget">
        <SourceBadge datasetKey="ic3_geographic" className="widget-source-badge" />
        <CyberSecurityMap data={geographicThreats} loading={loading} />
      </div>
      <div className="incident-landscape-widget">
        <SourceBadge datasetKey="ic3_sector_attack_matrix" className="widget-source-badge" />
        <SectorAttackHeatmap data={sectorAttackMatrix} loading={loading} />
      </div>
      <div className="incident-landscape-widget">
        <SourceBadge datasetKey="ic3_incidents" className="widget-source-badge" />
        <SectorImpactTable data={industryRisk} loading={loading} />
      </div>
      <div className="incident-landscape-widget">
        <SourceBadge datasetKey="ic3_incidents" className="widget-source-badge" />
        <LossByAttackTypeChart data={attackTypes} loading={loading} />
      </div>
      <div className="incident-landscape-widget">
        <SourceBadge datasetKey="ic3_incidents" className="widget-source-badge" />
        <MalwareBarChart data={attackTypes} loading={loading} />
      </div>
    </section>
  );
};

export default IncidentLandscape;
