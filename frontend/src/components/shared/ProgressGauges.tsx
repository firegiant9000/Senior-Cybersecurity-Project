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
    kevTotal: number;
    loading: boolean;
}

interface GaugeProps {
    value: number;
    label: string;
    sublabel?: string;
    color: string;
}

const BG_DATA = [{ value: 1, fill: 'rgba(148,163,184,0.35)' }];

const Gauge: React.FC<GaugeProps> = ({ value, label, sublabel, color }) => {
    const fillEndAngle = Math.round(180 - (value / 100) * 180);
    const fgData = [{ value: 1, fill: color }];

    return (
        <div className="gauge-item">
            <div className="gauge-chart-wrapper">
                <ResponsiveContainer width="100%" height={90}>
                    <RadialBarChart
                        innerRadius="60%" outerRadius="90%"
                        startAngle={180} endAngle={0}
                        data={BG_DATA} barSize={12}
                    >
                        <RadialBar dataKey="value" cornerRadius={6} />
                    </RadialBarChart>
                </ResponsiveContainer>
                <ResponsiveContainer width="100%" height={90}
                    style={{ position: 'absolute', top: 0, left: 0 }}>
                    <RadialBarChart
                        innerRadius="60%" outerRadius="90%"
                        startAngle={180} endAngle={fillEndAngle}
                        data={fgData} barSize={12}
                    >
                        <RadialBar dataKey="value" cornerRadius={6} />
                    </RadialBarChart>
                </ResponsiveContainer>
            </div>
            <span className="gauge-value" style={{ color, fontSize: 22 }}>{value}%</span>
            <span className="gauge-label">{label}</span>
            {sublabel && <span className="gauge-sublabel">{sublabel}</span>}
        </div>
    );
};

const ProgressGauges: React.FC<Props> = ({ data, kevTotal, loading }) => {
    if (loading) return (
        <div className="card progress-widget gauges-card">
            <span className="gauges-title">SECURITY POSTURE</span>
            <WidgetSkeleton variant="chart" />
        </div>
    );

    const total         = data.reduce((sum, d) => sum + d.count, 0);
    const criticalCount = data.find(d => d.severity === 'Critical')?.count ?? 0;
    const criticalPct   = total > 0 ? Math.round((criticalCount / total) * 100) : 0;
    const nonCritPct    = total > 0 ? Math.round(((total - criticalCount) / total) * 100) : 0;
    const kevSafePct    = total > 0 ? Math.round(((total - kevTotal) / total) * 100) : 0;

    return (
        <div className="card progress-widget gauges-card">
            <span className="gauges-title">SECURITY POSTURE</span>
            <div className="gauges-row">
                <Gauge value={nonCritPct} label="Non-Critical CVEs" sublabel="NVD" color="#00bcd4" />
                <Gauge value={criticalPct} label="Critical CVEs" sublabel="NVD" color="#d32f2f" />
                <Gauge value={kevSafePct} label="Not Actively Exploited" sublabel="NVD + CISA KEV" color="#4caf50" />
            </div>
        </div>
    );
};

export default ProgressGauges;
