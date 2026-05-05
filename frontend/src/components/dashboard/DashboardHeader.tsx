import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './DashboardHeader.css';

interface Props {
    dark: boolean;
    onToggleDark: () => void;
    user: { email: string | null } | null;
    onLogout: () => Promise<void>;
}

const DashboardHeader: React.FC<Props> = ({ dark, onToggleDark, user, onLogout }) => {
    const navigate = useNavigate();
    const { role, orgRole } = useAuth();
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement | null>(null);

    const canDebug = role === 'admin' || orgRole === 'admin' || orgRole === 'owner';
    const displayRole = orgRole ?? role ?? 'User';

    useEffect(() => {
        function handleOutside(e: MouseEvent) {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setMenuOpen(false);
            }
        }
        if (menuOpen) document.addEventListener('mousedown', handleOutside);
        return () => document.removeEventListener('mousedown', handleOutside);
    }, [menuOpen]);

    return (
        <header className="dashboard-header">
            <div className="header-logo-section">
                <img src="/logo.png" alt="Hacker Tracker" className="dashboard-header-logo" />
                <h1 className="header-title">Hacker Tracker</h1>
            </div>

            <div className="header-buttons">
                <div className="quick-actions">
                    <button className="dark-mode-btn" onClick={onToggleDark} title="Toggle dark mode">
                        {dark ? '☀' : '🌙'}
                    </button>
                    <button
                        className="dark-mode-btn glossary-btn"
                        onClick={() => navigate('/glossary')}
                        title="Glossary & help"
                        aria-label="Open glossary"
                    >
                        ?
                    </button>
                </div>

                {user ? (
                    <>
                        <div className="user-dropdown" ref={menuRef}>
                            <button
                                className="user-avatar-btn"
                                aria-haspopup="true"
                                aria-expanded={menuOpen}
                                onClick={() => setMenuOpen((s) => !s)}
                                title="Open profile menu"
                                aria-label="Open profile menu"
                            >
                                <span className="avatar-initials" aria-hidden="true">{user.email ? user.email.charAt(0).toUpperCase() : 'U'}</span>
                                <span className="avatar-label">{user.email ? user.email.split('@')[0] : 'User'}</span>
                                <span className="avatar-chevron" aria-hidden="true">▾</span>
                            </button>

                            <div className={`user-dropdown-menu ${menuOpen ? 'open' : ''}`} role="menu">
                                <div className="user-dropdown-item email" role="none">{user.email}</div>
                                <div className="user-dropdown-item role" role="none">{displayRole}</div>
                                <button className="user-dropdown-item" role="menuitem" onClick={() => { setMenuOpen(false); navigate('/org-profile'); }}>
                                    Organization Profile
                                </button>
                                <button className="user-dropdown-item" role="menuitem" onClick={() => { setMenuOpen(false); navigate('/settings'); }}>
                                    Settings
                                </button>
                                {canDebug && (
                                    <button className="user-dropdown-item" role="menuitem" onClick={() => { setMenuOpen(false); navigate('/settings/assessment-debug'); }}>
                                        Assessment Debug
                                    </button>
                                )}
                                <button className="user-dropdown-item" role="menuitem" onClick={async () => { await onLogout(); navigate('/'); }}>
                                    Log Out
                                </button>
                            </div>
                        </div>
                    </>
                ) : (
                    <>
                        <button onClick={() => navigate('/login')}>Log In</button>
                        <button onClick={() => navigate('/login')}>Sign Up</button>
                    </>
                )}
            </div>
        </header>
    );
};

export default DashboardHeader;
