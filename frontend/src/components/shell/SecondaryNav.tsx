import React from 'react';
import { Link } from 'react-router-dom';
import type { NavItem } from '../../config/navigation';
import '../dashboard/SubTabBar.css';

interface Props {
  items: NavItem[];
  activeItemId: string | null;
}

const SecondaryNav: React.FC<Props> = ({ items, activeItemId }) => {
  if (items.length === 0) return null;
  return (
    <nav aria-label="Section">
      <div className="sub-tabs-container">
        {items.map(({ id, label, to }) => (
          <Link
            key={id}
            to={to}
            className={`sub-tab ${activeItemId === id ? 'active' : ''}`}
            aria-current={activeItemId === id ? 'page' : undefined}
          >
            {label}
          </Link>
        ))}
      </div>
    </nav>
  );
};

export default SecondaryNav;
