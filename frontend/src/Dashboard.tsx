import React from 'react';
import './Dashboard.css';

const Dashboard: React.FC = () => {
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

            {/* Main Grid Layout */}
            <main className="dashboard-grid">
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

            </main>
        </div>
        

    )

}
export default Dashboard;