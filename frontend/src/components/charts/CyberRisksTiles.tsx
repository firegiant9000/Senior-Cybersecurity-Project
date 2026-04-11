import React from 'react';
import type { AttackTypeStats } from '../../api/dashboardSummary';
import { TILE_PALETTE } from '../../theme';
import WidgetSkeleton from '../shared/WidgetSkeleton';

interface Props {
    data: AttackTypeStats[];
    loading: boolean;
}

const CyberRisksTiles: React.FC<Props> = ({ data, loading }) => {
    if (loading) return <WidgetSkeleton variant="chart" />;
    if (data.length === 0) return <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>;

    const sorted = [...data]
        .sort((a, b) => b.complaint_count - a.complaint_count)
        .slice(0, 5);

    const total = sorted.reduce((sum, d) => sum + d.complaint_count, 0);
    const count = sorted.length;

    // Grid layout adapts: first tile spans 2 rows only when we have ≥ 3 items
    const firstSpans = count >= 3;

    return (
        <div
            className="risks-tiles-grid"
            style={{
                gridTemplateColumns: count <= 2 ? '1fr' : '1fr 1fr',
                gridTemplateRows: firstSpans ? '1fr 1fr 1fr' : 'auto',
            }}
        >
            {sorted.map((item, i) => {
                const pct = total > 0 ? Math.round((item.complaint_count / total) * 100) : 0;
                return (
                    <div
                        key={item.attack_type}
                        className={`risks-tile${i === 0 && firstSpans ? ' risks-tile--large' : ''}`}
                        style={{ backgroundColor: TILE_PALETTE[i % TILE_PALETTE.length] }}
                        title={`${item.attack_type}: ${item.complaint_count.toLocaleString()} complaints (${pct}%)`}
                    >
                        <span className="risks-tile-rank">{i + 1}. {item.attack_type}</span>
                        <span className="risks-tile-pct">{pct}%</span>
                    </div>
                );
            })}
        </div>
    );
};

export default CyberRisksTiles;
