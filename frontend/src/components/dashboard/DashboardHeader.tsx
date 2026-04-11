import React from 'react';
import { useNavigate } from 'react-router-dom';
import './DashboardHeader.css';

interface Props {
    dark: boolean;
    onToggleDark: () => void;
    user: { email: string | null } | null;
    onLogout: () => Promise<void>;
}

const DashboardHeader: React.FC<Props> = ({ dark, onToggleDark, user, onLogout }) => {
    const navigate = useNavigate();

    return (
        <header className="dashboard-header">
            <h1>Hacker Tracker</h1>
            <div className="header-buttons">
                <button className="dark-mode-btn" onClick={onToggleDark} title="Toggle dark mode">
                    {dark ? '☀' : '🌙'}
                </button>
                {user ? (
                    <>
                        <span className="header-user-email">{user.email}</span>
                        <button onClick={() => navigate('/settings')}>Settings</button>
                        <button onClick={async () => { await onLogout(); navigate('/login'); }}>Log Out</button>
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
