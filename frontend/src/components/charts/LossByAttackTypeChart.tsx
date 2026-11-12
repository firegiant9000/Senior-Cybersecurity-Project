import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
} from 'recharts';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import VictimImpactBadge from '../shared/VictimImpactBadge';
import { COLORS } from '../../theme';
import type { AttackTypeStats } from '../../api/dashboardSummary';
import {
  fmtMoney, truncate, TOOLTIP_CONTENT_STYLE, TOOLTIP_ITEM_STYLE, TOOLTIP_LABEL_STYLE,
} from '../../utils/chartFormat';

interface Props {
  data: AttackTypeStats[];
  loading: boolean;
}

export default function LossByAttackTypeChart({ data: attackTypes, loading }: Props) {
  const data = [...attackTypes]
    .sort((a, b) => b.total_loss - a.total_loss)
    .slice(0, 10)
    .map((d) => ({ ...d, label: truncate(d.attack_type) }));
  return (
    <WidgetErrorBoundary title="Loss by Attack Type">
      <div className="card chart-widget">
        <span className="widget-title">Total Financial Loss by Attack Type</span>
        <div className="chart-body">
          {loading ? <WidgetSkeleton variant="chart" /> : data.length === 0 ? (
            <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, left: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={fmtMoney} tick={{ fontSize: 12 }} tickMargin={8} />
                <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 12 }} tickMargin={8} />
                <Tooltip
                  contentStyle={TOOLTIP_CONTENT_STYLE}
                  itemStyle={TOOLTIP_ITEM_STYLE}
                  labelStyle={TOOLTIP_LABEL_STYLE}
                  formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, 'Total Loss']}
                  labelFormatter={(label: unknown) => { const m = data.find((d) => d.label === label); return m?.attack_type ?? String(label); }}
                />
                <Bar dataKey="total_loss" fill={COLORS.red} radius={[0, 4, 4, 0]}>
                  <LabelList dataKey="total_loss" position="right" formatter={(v: unknown) => fmtMoney(v as number)} style={{ fontSize: 10, fill: '#555', fontWeight: 600 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <VictimImpactBadge />
      </div>
    </WidgetErrorBoundary>
  );
}
