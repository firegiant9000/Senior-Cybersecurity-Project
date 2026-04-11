import React from 'react';
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts';
import type { IndustryRiskProfile } from '../../api/dashboardSummary';

interface Props {
    data: IndustryRiskProfile[];
    loading: boolean;
}

const COLOR_PALETTE = [
    '#d32f2f', '#1565c0', '#00838f', '#0b1060',
    '#c62828', '#006064', '#283593', '#37474f',
];

interface ContentProps {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    name?: string;
    index?: number;
    value?: number;
}

const CustomContent: React.FC<ContentProps> = ({
    x = 0, y = 0, width = 0, height = 0, name = '', index = 0, value = 0,
}) => {
    const color = COLOR_PALETTE[index % COLOR_PALETTE.length];

    // Scale font size with tile size, clamped between 9 and 15px
    const fontSize = Math.min(15, Math.max(9, Math.floor(width / 8)));
    // How many chars fit on one line given the font size (approx 0.58 char/px)
    const maxChars = Math.max(4, Math.floor((width - 8) / (fontSize * 0.58)));

    const displayName = name.length > maxChars ? name.slice(0, maxChars - 1) + '…' : name;

    const showName  = width > 30 && height > 24;
    const showCount = width > 40 && height > 44;
    const clipId    = `clip-${index}-${Math.round(x)}-${Math.round(y)}`;

    return (
        <g>
            <clipPath id={clipId}>
                <rect x={x + 1} y={y + 1} width={Math.max(0, width - 2)} height={Math.max(0, height - 2)} />
            </clipPath>
            <rect
                x={x} y={y} width={width} height={height}
                fill={color} stroke="#fff" strokeWidth={2} rx={2}
                clipPath={`url(#${clipId})`}
            />
            {showName && (
                <text
                    x={x + width / 2}
                    y={y + height / 2 + (showCount ? -(fontSize * 0.7) : 0)}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="white"
                    fontSize={fontSize}
                    fontWeight={700}
                    clipPath={`url(#${clipId})`}
                >
                    {displayName}
                </text>
            )}
            {showCount && (
                <text
                    x={x + width / 2}
                    y={y + height / 2 + fontSize * 0.9}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="rgba(255,255,255,0.8)"
                    fontSize={Math.max(8, fontSize - 2)}
                    fontWeight={400}
                    clipPath={`url(#${clipId})`}
                >
                    {value.toLocaleString()}
                </text>
            )}
        </g>
    );
};

const CyberRisksTreemap: React.FC<Props> = ({ data, loading }) => {
    if (loading) return <p style={{ color: '#888', fontSize: 13 }}>Loading…</p>;
    if (data.length === 0) return <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>;

    const chartData = [...data]
        .sort((a, b) => b.complaint_count - a.complaint_count)
        .slice(0, 8)
        .map(d => ({ name: d.sector, value: d.complaint_count }));

    return (
        <ResponsiveContainer width="100%" height="100%">
            <Treemap
                data={chartData}
                dataKey="value"
                content={<CustomContent />}
            >
                <Tooltip
                    formatter={(value: unknown) => [(value as number).toLocaleString(), 'Complaints']}
                />
            </Treemap>
        </ResponsiveContainer>
    );
};

export default CyberRisksTreemap;
