import React from 'react';
import type { TabGroupDef } from '../../config/tabGroups';
import './TabBar.css';

interface Props {
    activeGroup: string;
    onGroupChange: (id: string) => void;
    groups: TabGroupDef[];
}

const TabBar: React.FC<Props> = ({ activeGroup, onGroupChange, groups }) => {
    const handleKeyDown = (e: React.KeyboardEvent, idx: number) => {
        let next = -1;
        if (e.key === 'ArrowRight') next = (idx + 1) % groups.length;
        else if (e.key === 'ArrowLeft') next = (idx - 1 + groups.length) % groups.length;
        else if (e.key === 'Home') next = 0;
        else if (e.key === 'End') next = groups.length - 1;
        if (next >= 0) {
            e.preventDefault();
            onGroupChange(groups[next].id);
            (e.currentTarget.parentElement?.children[next] as HTMLElement)?.focus();
        }
    };

    return (
        <>
            {/* Desktop/tablet: horizontal scrolling tab strip */}
            <div className="tabs-container" role="tablist">
                {groups.map(({ id, label }, idx) => (
                    <button
                        key={id}
                        role="tab"
                        aria-selected={activeGroup === id}
                        tabIndex={activeGroup === id ? 0 : -1}
                        className={`tab ${activeGroup === id ? 'active' : ''}`}
                        onClick={() => onGroupChange(id)}
                        onKeyDown={(e) => handleKeyDown(e, idx)}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* Mobile: native select dropdown with optgroup for sub-tabs */}
            <select
                className="tabs-select"
                value={activeGroup}
                onChange={(e) => onGroupChange(e.target.value)}
                aria-label="Navigate to tab"
            >
                {groups.map(({ id, label }) => (
                    <option key={id} value={id}>{label}</option>
                ))}
            </select>
        </>
    );
};

export default TabBar;
