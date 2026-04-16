import React from 'react';
import type { SubTabDef } from '../../config/tabGroups';
import './SubTabBar.css';

interface Props {
  subTabs: SubTabDef[];
  activeSubTab: string;
  onSubTabChange: (id: string) => void;
}

const SubTabBar: React.FC<Props> = ({ subTabs, activeSubTab, onSubTabChange }) => {
  const handleKeyDown = (e: React.KeyboardEvent, idx: number) => {
    let next = -1;
    if (e.key === 'ArrowRight') next = (idx + 1) % subTabs.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + subTabs.length) % subTabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = subTabs.length - 1;
    if (next >= 0) {
      e.preventDefault();
      onSubTabChange(subTabs[next].id);
      (e.currentTarget.parentElement?.children[next] as HTMLElement)?.focus();
    }
  };

  return (
    <div className="sub-tabs-container" role="tablist" aria-label="Sub-navigation">
      {subTabs.map(({ id, label }, idx) => (
        <button
          key={id}
          role="tab"
          aria-selected={activeSubTab === id}
          tabIndex={activeSubTab === id ? 0 : -1}
          className={`sub-tab ${activeSubTab === id ? 'active' : ''}`}
          onClick={() => onSubTabChange(id)}
          onKeyDown={(e) => handleKeyDown(e, idx)}
        >
          {label}
        </button>
      ))}
    </div>
  );
};

export default SubTabBar;
