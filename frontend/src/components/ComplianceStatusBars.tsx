import React from 'react';

interface ComplianceItem {
    name: string;
    percent: number;
    color: string;
}

const COMPLIANCE_ITEMS: ComplianceItem[] = [
    { name: 'PCI DSS', percent: 43, color: '#00bcd4' },
    { name: 'SOC 2',   percent: 65, color: '#00838f' },
];

const ComplianceStatusBars: React.FC = () => {
    return (
        <div className="card compliance-widget compliance-bars-card">
            <span className="compliance-bars-title">
                COMPLIANCE STATUS
                <span style={{ fontSize: 9, fontWeight: 500, opacity: 0.6, marginLeft: 6, letterSpacing: 0 }}>
                    (DEMO)
                </span>
            </span>
            <div className="compliance-bars-list">
                {COMPLIANCE_ITEMS.map((item) => (
                    <div key={item.name} className="compliance-bar-row">
                        <div className="compliance-bar-header">
                            <span className="compliance-bar-name">{item.name}</span>
                            <span className="compliance-bar-percent">{item.percent} %</span>
                        </div>
                        <div className="compliance-bar-track">
                            <div
                                className="compliance-bar-fill"
                                style={{ width: `${item.percent}%`, backgroundColor: item.color }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ComplianceStatusBars;
