import React from 'react';
import {
    RadialBarChart,
    RadialBar,
    ResponsiveContainer,
} from 'recharts';
import type { SeverityCount } from '../../api/dashboardSummary';
import WidgetSkeleton from './WidgetSkeleton';

interface Props {
    data: SeverityCount[];
    loading: boolean;
}

interface GaugeProps {
    value: number;
    label: string;
    color: string;
}

const Gauge: React.FC<GaugeProps> = ({ value, label, color }) => {
    // RadialBarChart expects data on the chart itself, not on RadialBar
    const chartData = [{ value, fill: color }];

    return (
        <div className="gauge-item">
            <ResponsiveContainer width="100%" height={130}>
                <RadialBarChart
                    innerRadius="60%"
                    outerRadius="90%"
                    startAngle={180}
                    endAngle={0}
                    data={chartData}
                    barSize={14}
                >
                    <RadialBar
                        dataKey="value"
                        cornerRadius={7}
                        background={{ fill: 'rgba(255,255,255,0.15)' }}
                    />
                </RadialBarChart>
            </ResponsiveContainer>
            <span className="gauge-value" style={{ color }}>{value}%</span>
            <span className="gauge-label">{label}</span>
        </div>
    );
};

const ProgressGauges: React.FC<Props> = ({ data, loading }) => {
    if (loading) return (
        <div className="card progress-widget gauges-card">
            <span className="gauges-title">PROGRESSION</span>
            <WidgetSkeleton variant="chart" />
        </div>
    );

    const total = data.reduce((sum, d) => sum + d.count, 0);
    const criticalCount = data.find(d => d.severity === 'Critical')?.count ?? 0;

    const criticalPct = total > 0 ? Math.round((criticalCount / total) * 100) : 0;
    const overallPct  = total > 0 ? Math.round(((total - criticalCount) / total) * 100) : 0;

    return (
        <div className="card progress-widget gauges-card">
            <span className="gauges-title">PROGRESSION</span>
            <div className="gauges-row">
                <Gauge value={overallPct}  label="Overall"        color="#00bcd4" />
                <Gauge value={criticalPct} label="Critical Risks" color="#d32f2f" />
            </div>
        </div>
    );
};

export default ProgressGauges;
