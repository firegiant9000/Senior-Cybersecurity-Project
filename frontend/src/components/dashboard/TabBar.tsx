import React from 'react';
import './TabBar.css';

export interface TabDef {
    id: string;
    label: string;
}

interface Props {
    activeTab: string;
    onTabChange: (id: string) => void;
    tabs: TabDef[];
}

const TabBar: React.FC<Props> = ({ activeTab, onTabChange, tabs }) => (
    <>
        {/* Desktop/tablet: horizontal scrolling tab strip */}
        <div className="tabs-container" role="tablist">
            {tabs.map(({ id, label }) => (
                <button
                    key={id}
                    role="tab"
                    aria-selected={activeTab === id}
                    className={`tab ${activeTab === id ? 'active' : ''}`}
                    onClick={() => onTabChange(id)}
                >
                    {label}
                </button>
            ))}
        </div>

        {/* Mobile: native select dropdown — all tabs always reachable */}
        <select
            className="tabs-select"
            value={activeTab}
            onChange={(e) => onTabChange(e.target.value)}
            aria-label="Navigate to tab"
        >
            {tabs.map(({ id, label }) => (
                <option key={id} value={id}>{label}</option>
            ))}
        </select>
    </>
);

export default TabBar;
