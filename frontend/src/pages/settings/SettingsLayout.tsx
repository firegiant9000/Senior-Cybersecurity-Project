import { NavLink, Outlet } from 'react-router-dom';
import { SETTINGS_ITEMS } from '../../config/navigation';
import '../SettingsPage.css';

export default function SettingsLayout() {
  return (
    <div>
      <h1>Settings</h1>
      <div className="settings-area-body">
        <nav aria-label="Settings" className="settings-area-menu">
          {SETTINGS_ITEMS.map((item) => (
            <NavLink key={item.id} to={item.to}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="settings-area-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
