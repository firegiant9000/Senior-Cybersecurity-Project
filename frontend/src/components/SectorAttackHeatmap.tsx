import React, { useMemo } from 'react';
import type { SectorAttackCombination } from '../api/dashboardSummary';
import WidgetSkeleton from './WidgetSkeleton';

interface Props {
    data: SectorAttackCombination[];
    loading: boolean;
}

/** Interpolate from white → navy based on 0–1 ratio. */
function cellColor(ratio: number): string {
    if (ratio <= 0) return '#f8fafc';
    // white → teal (#00bcd4) → navy (#0b1060)
    if (ratio < 0.5) {
        const t = ratio / 0.5;
        const r = Math.round(255 + (0 - 255) * t);
        const g = Math.round(255 + (188 - 255) * t);
        const b = Math.round(255 + (212 - 255) * t);
        return `rgb(${r},${g},${b})`;
    }
    const t = (ratio - 0.5) / 0.5;
    const r = Math.round(0 + (11 - 0) * t);
    const g = Math.round(188 + (16 - 188) * t);
    const b = Math.round(212 + (96 - 212) * t);
    return `rgb(${r},${g},${b})`;
}

function textColor(ratio: number): string {
    return ratio > 0.45 ? '#ffffff' : '#1a1a2e';
}

function fmtK(v: number): string {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000)     return `${Math.round(v / 1_000)}k`;
    return String(v);
}

const TOP_SECTORS = 6;
const TOP_ATTACKS = 7;

const SectorAttackHeatmap: React.FC<Props> = ({ data, loading }) => {
    if (loading) return <WidgetSkeleton variant="chart" />;
    if (data.length === 0) return <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>;

    const { sectors, attacks, grid, maxVal } = useMemo(() => {
        // Aggregate complaint counts by sector and attack type
        const sectorTotals: Record<string, number> = {};
        const attackTotals: Record<string, number> = {};
        const cellMap: Record<string, number> = {};

        for (const row of data) {
            sectorTotals[row.sector]      = (sectorTotals[row.sector]      ?? 0) + row.complaint_count;
            attackTotals[row.attack_type] = (attackTotals[row.attack_type] ?? 0) + row.complaint_count;
            cellMap[`${row.sector}||${row.attack_type}`] = row.complaint_count;
        }

        const sectors = Object.entries(sectorTotals)
            .sort((a, b) => b[1] - a[1])
            .slice(0, TOP_SECTORS)
            .map(([s]) => s);

        const attacks = Object.entries(attackTotals)
            .sort((a, b) => b[1] - a[1])
            .slice(0, TOP_ATTACKS)
            .map(([a]) => a);

        let maxVal = 0;
        for (const s of sectors) {
            for (const a of attacks) {
                const v = cellMap[`${s}||${a}`] ?? 0;
                if (v > maxVal) maxVal = v;
            }
        }

        const grid: number[][] = sectors.map(s =>
            attacks.map(a => cellMap[`${s}||${a}`] ?? 0)
        );

        return { sectors, attacks, grid, maxVal };
    }, [data]);

    // Truncate long names for display
    const truncate = (s: string, n: number) => s.length > n ? s.slice(0, n) + '…' : s;

    return (
        <div className="heatmap-wrapper">
            <div className="heatmap-scroll">
                <table className="heatmap-table">
                    <thead>
                        <tr>
                            <th className="heatmap-corner">Sector ↓ / Attack Type →</th>
                            {attacks.map(a => (
                                <th key={a} className="heatmap-col-header" title={a}>
                                    {truncate(a, 18)}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {sectors.map((s, si) => (
                            <tr key={s}>
                                <td className="heatmap-row-header" title={s}>
                                    {truncate(s, 20)}
                                </td>
                                {grid[si].map((val, ai) => {
                                    const ratio = maxVal > 0 ? val / maxVal : 0;
                                    return (
                                        <td
                                            key={attacks[ai]}
                                            className="heatmap-cell"
                                            style={{
                                                backgroundColor: cellColor(ratio),
                                                color: textColor(ratio),
                                            }}
                                            title={`${s} × ${attacks[ai]}: ${val.toLocaleString()} complaints`}
                                        >
                                            {val > 0 ? fmtK(val) : ''}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="heatmap-note">
                Top {TOP_SECTORS} sectors × top {TOP_ATTACKS} attack types by complaint volume.
                Darker = more complaints.
            </p>
        </div>
    );
};

export default SectorAttackHeatmap;
