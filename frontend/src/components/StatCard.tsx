import React from 'react';

interface Props {
    title: string;
    value: string | number;
    valueColor?: string;
    change?: string;       // e.g. "+9%" or "-2%"
    changeNote?: string;   // e.g. "to previous 3 months"
}

const StatCard: React.FC<Props> = ({
    title,
    value,
    valueColor = '#00bcd4',
    change,
    changeNote,
}) => {
    const changePositive = change?.startsWith('+');
    const changeColor = changePositive ? '#2e7d32' : '#c62828';

    return (
        <div className="card overview-stat-card">
            <span className="overview-stat-title">{title}</span>
            <div className="overview-stat-value-row">
                <span className="overview-stat-value" style={{ color: valueColor }}>
                    {typeof value === 'number' ? value.toLocaleString() : value}
                </span>
                {change && (
                    <span className="overview-stat-change" style={{ color: changeColor }}>
                        ({change})
                    </span>
                )}
            </div>
            {changeNote && (
                <span className="overview-stat-subtitle">{changeNote}</span>
            )}
        </div>
    );
};

export default StatCard;
