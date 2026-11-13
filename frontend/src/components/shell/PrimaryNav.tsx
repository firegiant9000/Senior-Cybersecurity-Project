import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { NavGroup } from '../../config/navigation';
import '../dashboard/TabBar.css';

interface Props {
  groups: NavGroup[];
  activeGroupId: string | null;
  activeItemId?: string | null;
}

const PrimaryNav: React.FC<Props> = ({ groups, activeGroupId, activeItemId = null }) => {
  const navigate = useNavigate();

  const activeGroup = groups.find((g) => g.id === activeGroupId);
  const activeItem = activeGroup?.items.find((i) => i.id === activeItemId);
  const selectValue = activeItem?.to ?? activeGroup?.to ?? '';

  return (
    <nav aria-label="Primary">
      <div className="tabs-container">
        {groups.map(({ id, label, to }) => (
          <Link
            key={id}
            to={to}
            className={`tab ${activeGroupId === id ? 'active' : ''}`}
            aria-current={activeGroupId === id ? 'page' : undefined}
          >
            {label}
          </Link>
        ))}
      </div>

      {/* Mobile: native select listing every visible item. With no active page (e.g. /settings)
          a disabled placeholder keeps "Overview" selectable. */}
      <select
        className="tabs-select"
        value={selectValue}
        onChange={(e) => navigate(e.target.value)}
        aria-label="Navigate to page"
      >
        {selectValue === '' && <option value="" disabled>Choose a page</option>}
        {groups.map(({ id, label, to, items }) =>
          items.length > 0 ? (
            <optgroup key={id} label={label}>
              {items.map((item) => (
                <option key={item.id} value={item.to}>{item.label}</option>
              ))}
            </optgroup>
          ) : (
            <option key={id} value={to}>{label}</option>
          ),
        )}
      </select>
    </nav>
  );
};

export default PrimaryNav;
