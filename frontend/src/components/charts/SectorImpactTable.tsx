import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import VictimImpactBadge from '../shared/VictimImpactBadge';
import type { IndustryRiskProfile } from '../../api/dashboardSummary';

interface Props {
  data: IndustryRiskProfile[];
  loading: boolean;
}

export default function SectorImpactTable({ data, loading }: Props) {
  return (
    <WidgetErrorBoundary title="Sector Summary">
      <div className="card victim-table-card">
        <span className="widget-title">Sector Impact Summary</span>
        <div className="tab-table-scroll">
          {loading ? <WidgetSkeleton variant="chart" /> : data.length === 0 ? (
            <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
          ) : (
            <table className="tab-table">
              <thead>
                <tr>
                  <th>Sector</th>
                  <th>Complaints</th>
                  <th>Total Loss</th>
                  <th>Avg Loss / Incident</th>
                </tr>
              </thead>
              <tbody>
                {[...data].sort((a, b) => b.total_loss - a.total_loss).map(row => (
                  <tr key={row.sector}>
                    <td>{row.sector}</td>
                    <td>{row.complaint_count.toLocaleString()}</td>
                    <td>${row.total_loss.toLocaleString()}</td>
                    <td>${row.avg_loss_per_incident.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <VictimImpactBadge />
      </div>
    </WidgetErrorBoundary>
  );
}
