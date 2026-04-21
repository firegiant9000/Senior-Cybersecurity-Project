import React from 'react';
import type { TabGroupDef } from '../../config/tabGroups';
import './TabBar.css';

interface Props {
    activeGroup: string;
    activeSubTab?: string;
    onGroupChange: (id: string) => void;
    onSubTabChange?: (subId: string, groupId: string) => void;
    groups: TabGroupDef[];
}

const TabBar: React.FC<Props> = ({ activeGroup, activeSubTab, onGroupChange, onSubTabChange, groups }) => {
    const handleKeyDown = (e: React.KeyboardEvent, idx: number) => {
        let next = -1;
        if (e.key === 'ArrowRight') next = (idx + 1) % groups.length;
        else if (e.key === 'ArrowLeft') next = (idx - 1 + groups.length) % groups.length;
        else if (e.key === 'Home') next = 0;
        else if (e.key === 'End') next = groups.length - 1;
        if (next >= 0) {
            e.preventDefault();
            if (!groups[next].locked) onGroupChange(groups[next].id);
            (e.currentTarget.parentElement?.children[next] as HTMLElement)?.focus();
        }
    };

    // Determine the value shown in the mobile select:
    // use the active sub-tab ID when in a group with sub-tabs, else the group ID.
    const currentGroupDef = groups.find((g) => g.id === activeGroup);
    const selectValue = currentGroupDef?.subTabs && activeSubTab ? activeSubTab : activeGroup;

    const handleSelectChange = (value: string) => {
        for (const group of groups) {
            if (group.locked) continue;
            if (!group.subTabs) {
                if (group.id === value) { onGroupChange(value); return; }
            } else {
                const sub = group.subTabs.find((s) => s.id === value);
                if (sub) { onSubTabChange?.(value, group.id); return; }
            }
        }
    };

    return (
        <>
            {/* Desktop/tablet: horizontal scrolling tab strip */}
            <div className="tabs-container" role="tablist">
                {groups.map(({ id, label, subTabs, locked }, idx) => (
                    <button
                        key={id}
                        role="tab"
                        aria-selected={!locked && activeGroup === id}
                        aria-disabled={locked || undefined}
                        tabIndex={activeGroup === id ? 0 : -1}
                        className={`tab ${activeGroup === id ? 'active' : ''} ${locked ? 'tab--locked' : ''}`}
                        onClick={() => { if (!locked) onGroupChange(id); }}
                        onKeyDown={(e) => handleKeyDown(e, idx)}
                        title={locked ? 'Complete org setup to unlock' : undefined}
                    >
                        {locked && <span className="tab-lock-icon" aria-hidden="true">🔒</span>}
                        {label}
                        {!locked && subTabs && subTabs.length > 0 && (
                            <span className={`tab-chevron${activeGroup === id ? ' tab-chevron--open' : ''}`} aria-hidden="true">▾</span>
                        )}
                    </button>
                ))}
            </div>

            {/* Mobile: native select with optgroup for groups that have sub-tabs */}
            <select
                className="tabs-select"
                value={selectValue}
                onChange={(e) => handleSelectChange(e.target.value)}
                aria-label="Navigate to tab"
            >
                {groups.map(({ id, label, subTabs, locked }) => {
                    if (locked) {
                        return <option key={id} value={id} disabled>🔒 {label}</option>;
                    }
                    if (subTabs && subTabs.length > 0) {
                        return (
                            <optgroup key={id} label={label}>
                                {subTabs.map((sub) => (
                                    <option key={sub.id} value={sub.id}>{sub.label}</option>
                                ))}
                            </optgroup>
                        );
                    }
                    return <option key={id} value={id}>{label}</option>;
                })}
            </select>
        </>
    );
};

export default TabBar;
