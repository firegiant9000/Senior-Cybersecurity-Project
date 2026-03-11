import React, { useState } from 'react';
import './Dashboard.css';
import EconomicsTable from './components/EconomicsTable';
import CisaKevTable from './components/CisaKevTable';
import NvdTable from './components/NvdTable';
import IC3Table from './components/IC3Table';

const API_BASE_URL =
    (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
        .VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

const Dashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState('overview');

    return (
        <div className="dashboard-container">
            {/* Header */}
            <header className="dashboard-header">
                <h1> HACKER TRACKER 🤖</h1>
                <div className="header-buttons">
                    <button>Settings</button>
                    <button>Log In</button>
                    <button>Sign Up</button>
                </div>
            </header>

            {/* Tabs */}
            <div className="tabs-container">
                <button
                    className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                >
                    Overview
                </button>
                <button
                    className={`tab ${activeTab === 'economics' ? 'active' : ''}`}
                    onClick={() => setActiveTab('economics')}
                >
                    Economics
                </button>
                <button
                    className={`tab ${activeTab === 'cisa' ? 'active' : ''}`}
                    onClick={() => setActiveTab('cisa')}
                >
                    CISA KEV
                </button>
                <button
                    className={`tab ${activeTab === 'nvd' ? 'active' : ''}`}
                    onClick={() => setActiveTab('nvd')}
                >
                    NVD
                </button>
                <button
                    className={`tab ${activeTab === 'ic3' ? 'active' : ''}`}
                    onClick={() => setActiveTab('ic3')}
                >
                    IC3
                </button>
            </div>

            {/* Main Content */}
            <main className="dashboard-content">
                {activeTab === 'overview' && (
                    <div className="dashboard-grid">
                        {/* Top Row */}
                        <div className="card map-widget">Cyber Security Map</div>
                        <div className="card malware-widget">Intrustion Attempts by Malware</div>
                        <div className="card stat-card">Total Intrusion Attempts<br/><h2>200</h2></div>
                        <div className="card stat-card">Backup Frequency<br/><h2>10.2</h2></div>

                        {/* Middle Row */}
                        <div className="card progress-weight">Progression</div>
                        <div className="card compliance-weight">Compliance Status</div>
                        <div className="card stat-card">Mean Detect Time<br/><h2>9.4</h2></div>
                        <div className="card stat-card">Mean Resolve Time<br/><h2>39</h2></div>

                        {/*Bottom Row */}
                        <div className="card incident-weight">Incident Management</div>
                        <div className="card risk-widget">Top Cyber Security Risks</div>
                    </div>
                )}

                {activeTab === 'economics' && <EconomicsTable apiBaseUrl={API_BASE_URL} />}
                {activeTab === 'cisa' && <CisaKevTable apiBaseUrl={API_BASE_URL} />}
                {activeTab === 'nvd' && <NvdTable apiBaseUrl={API_BASE_URL} />}
                {activeTab === 'ic3' && <IC3Table apiBaseUrl={API_BASE_URL} />}
            </main>
        </div>
    );
};

export default Dashboard;
