import React from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from 'recharts';
import type { SectorAttackCombination } from '../../api/dashboardSummary';

interface Props {
    data: SectorAttackCombination[];
    loading: boolean;
}

// Classify each attack type into a risk tier based on typical IC3 impact levels
const CRITICAL_TYPES = new Set([
    'business email compromise', 'investment', 'ransomware', 'data breach',
    'corporate data breach', 'real estate/rental', 'government impersonation',
]);
const HIGH_TYPES = new Set([
    'extortion', 'confidence fraud/romance', 'identity theft', 'wire fraud',
    'non-payment/non-delivery', 'advanced fee', 'lottery/sweepstakes',
]);
// Everything else maps to Medium

function classifyAttackType(attack_type: string): 'Medium' | 'High' | 'Critical' {
    const lower = attack_type.toLowerCase();
    if ([...CRITICAL_TYPES].some(t => lower.includes(t))) return 'Critical';
    if ([...HIGH_TYPES].some(t => lower.includes(t))) return 'High';
    return 'Medium';
}

function truncate(str: string, max = 12): string {
    return str.length > max ? str.slice(0, max) + '…' : str;
}

const IncidentManagementChart: React.FC<Props> = ({ data, loading }) => {
    if (loading) return <p style={{ color: '#888', fontSize: 13 }}>Loading…</p>;
    if (data.length === 0) return <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>;

    // Aggregate by sector → { Medium, High, Critical }
    const sectorMap: Record<string, { Medium: number; High: number; Critical: number; total: number }> = {};
    for (const row of data) {
        if (!sectorMap[row.sector]) {
            sectorMap[row.sector] = { Medium: 0, High: 0, Critical: 0, total: 0 };
        }
        const tier = classifyAttackType(row.attack_type);
        sectorMap[row.sector][tier] += row.complaint_count;
        sectorMap[row.sector].total  += row.complaint_count;
    }

    const chartData = Object.entries(sectorMap)
        .sort((a, b) => b[1].total - a[1].total)
        .slice(0, 6)
        .map(([sector, counts]) => ({
            sector: truncate(sector),
            Medium:   counts.Medium,
            High:     counts.High,
            Critical: counts.Critical,
        }));

    return (
        <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="sector" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                    formatter={(value: unknown, name: unknown) =>
                        [(value as number).toLocaleString(), name as string]
                    }
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Medium"   fill="#00bcd4" radius={[4, 4, 0, 0]} />
                <Bar dataKey="High"     fill="#0b1060" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Critical" fill="#d32f2f" radius={[4, 4, 0, 0]} />
            </BarChart>
        </ResponsiveContainer>
    );
};

export default IncidentManagementChart;
