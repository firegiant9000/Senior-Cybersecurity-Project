import React, { useState, useEffect } from 'react';
import './Dashboard.css';

interface EconomicsItem {
    id: number;
    state: string;
    smb_count: number;
    avg_revenue: number;
}

interface CISAVulnerability {
    id: string;
    vulnerability_name: string;
    vendor: string;
    product: string;
    severity_label: string;
    severity_score: number | null;
    is_kev: boolean;
    kev_date_added: string;
}

interface NVDCVEItem {
    id: string;
    description: string;
    severity_label: string;
    severity_score: number | null;
    published_date: string;
    last_modified: string;
}

interface ApiResponse<T> {
    total: number;
    page: number;
    page_size: number;
    items: T[];
}

const Dashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState('overview');
    const [economicsData, setEconomicsData] = useState<EconomicsItem[]>([]);
    const [economicsLoading, setEconomicsLoading] = useState(false);
    const [economicsError, setEconomicsError] = useState<string | null>(null);
    const [economicsPage, setEconomicsPage] = useState(1);
    const [economicsTotal, setEconomicsTotal] = useState(0);
    const [cisaData, setCisaData] = useState<CISAVulnerability[]>([]);
    const [cisaLoading, setCisaLoading] = useState(false);
    const [cisaError, setCisaError] = useState<string | null>(null);
    const [cisaPage, setCisaPage] = useState(1);
    const [cisaTotal, setCisaTotal] = useState(0);
    const [nvdData, setNvdData] = useState<NVDCVEItem[]>([]);
    const [nvdLoading, setNvdLoading] = useState(false);
    const [nvdError, setNvdError] = useState<string | null>(null);
    const [nvdPage, setNvdPage] = useState(1);
    const [nvdTotal, setNvdTotal] = useState(0);

    useEffect(() => {
        if (activeTab === 'economics') {
            fetchEconomicsData(1);
        } else if (activeTab === 'cisa') {
            fetchCisaData(1);
        } else if (activeTab === 'nvd') {
            fetchNvdData(1);
        }
    }, [activeTab]);

    const fetchEconomicsData = async (page: number) => {
        setEconomicsLoading(true);
        setEconomicsError(null);
        try {
            const baseUrl = `http://${window.location.hostname}:8000`;
            const response = await fetch(`${baseUrl}/api/v1/economics/indicators?page=${page}&page_size=10&sort_by=smb_count&sort_order=desc`);
            if (!response.ok) throw new Error(`Failed to fetch economics data: ${response.status}`);
            const data: ApiResponse<EconomicsItem> = await response.json();
            setEconomicsData(data.items);
            setEconomicsTotal(data.total);
            setEconomicsPage(page);
        } catch (err) {
            setEconomicsError(err instanceof Error ? err.message : 'Error fetching data');
        } finally {
            setEconomicsLoading(false);
        }
    };

    const fetchCisaData = async (page: number) => {
        setCisaLoading(true);
        setCisaError(null);
        try {
            const baseUrl = `http://${window.location.hostname}:8000`;
            const response = await fetch(`${baseUrl}/api/v1/vulnerabilities/exploited?page=${page}&page_size=10&sort_by=kev_date_added&sort_order=desc`);
            if (!response.ok) throw new Error(`Failed to fetch CISA KEV data: ${response.status}`);
            const data: ApiResponse<CISAVulnerability> = await response.json();
            setCisaData(data.items);
            setCisaTotal(data.total);
            setCisaPage(page);
        } catch (err) {
            setCisaError(err instanceof Error ? err.message : 'Error fetching data');
        } finally {
            setCisaLoading(false);
        }
    };

    const fetchNvdData = async (page: number) => {
        setNvdLoading(true);
        setNvdError(null);
        try {
            const baseUrl = `http://${window.location.hostname}:8000`;
            const url = `${baseUrl}/api/v1/nvd/cves?page=${page}&page_size=10`;
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to fetch NVD data: ${response.status} - ${errorText}`);
            }
            const data: ApiResponse<NVDCVEItem> = await response.json();
            setNvdData(data.items);
            setNvdTotal(data.total);
            setNvdPage(page);
        } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Unknown error fetching data';
            console.error('NVD fetch error:', errorMsg);
            setNvdError(errorMsg);
        } finally {
            setNvdLoading(false);
        }
    };

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

                {activeTab === 'economics' && (
                    <div className="data-table-container">
                        <h2>State Economic Indicators (BEA Data)</h2>
                        <div className="pagination-info">Showing {economicsData.length} of {economicsTotal} states</div>
                        {economicsLoading && <p>Loading economics data...</p>}
                        {economicsError && <p className="error">Error: {economicsError}</p>}
                        {economicsData.length > 0 && (
                            <>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>State</th>
                                            <th>SMB Count</th>
                                            <th>Avg Revenue ($)</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {economicsData.map((item) => (
                                            <tr key={item.id}>
                                                <td>{item.state}</td>
                                                <td>{item.smb_count.toLocaleString()}</td>
                                                <td>${(item.avg_revenue / 1e9).toFixed(2)}B</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                <div className="pagination-controls">
                                    <button 
                                        disabled={economicsPage === 1} 
                                        onClick={() => fetchEconomicsData(economicsPage - 1)}
                                    >
                                        ← Previous
                                    </button>
                                    <span>Page {economicsPage} of {Math.ceil(economicsTotal / 10)}</span>
                                    <button 
                                        disabled={economicsPage * 10 >= economicsTotal} 
                                        onClick={() => fetchEconomicsData(economicsPage + 1)}
                                    >
                                        Next →
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {activeTab === 'cisa' && (
                    <div className="data-table-container">
                        <h2>CISA KEV - Exploited Vulnerabilities ({cisaTotal} total)</h2>
                        <div className="pagination-info">Showing {cisaData.length} of {cisaTotal}</div>
                        {cisaLoading && <p>Loading CISA KEV data...</p>}
                        {cisaError && <p className="error">Error: {cisaError}</p>}
                        {cisaData.length > 0 && (
                            <>
                                <table className="data-table cisa-table">
                                    <thead>
                                        <tr>
                                            <th>CVE ID</th>
                                            <th>Vendor</th>
                                            <th>Product</th>
                                            <th>Vulnerability</th>
                                            <th>Date Added</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {cisaData.map((item) => (
                                            <tr key={item.id}>
                                                <td className="cve-id">{item.id}</td>
                                                <td>{item.vendor}</td>
                                                <td>{item.product}</td>
                                                <td className="vuln-name">{item.vulnerability_name.substring(0, 100)}...</td>
                                                <td>{item.kev_date_added}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                <div className="pagination-controls">
                                    <button 
                                        disabled={cisaPage === 1} 
                                        onClick={() => fetchCisaData(cisaPage - 1)}
                                    >
                                        ← Previous
                                    </button>
                                    <span>Page {cisaPage} of {Math.ceil(cisaTotal / 10)}</span>
                                    <button 
                                        disabled={cisaPage * 10 >= cisaTotal} 
                                        onClick={() => fetchCisaData(cisaPage + 1)}
                                    >
                                        Next →
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {activeTab === 'nvd' && (
                    <div className="data-table-container">
                        <h2>NVD - National Vulnerability Database ({nvdTotal} total)</h2>
                        <div className="pagination-info">Showing {nvdData.length} of {nvdTotal}</div>
                        {nvdLoading && <p>Loading NVD CVE data...</p>}
                        {nvdError && <p className="error">Error: {nvdError}</p>}
                        {nvdData.length > 0 && (
                            <>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>CVE ID</th>
                                            <th>Description</th>
                                            <th>Severity</th>
                                            <th>Score</th>
                                            <th>Published</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {nvdData.map((item) => (
                                            <tr key={item.id}>
                                                <td className="cve-id">
                                                    <a href={`https://nvd.nist.gov/vuln/detail/${item.id}`} target="_blank" rel="noopener noreferrer">
                                                        {item.id}
                                                    </a>
                                                </td>
                                                <td>{item.description.substring(0, 80)}...</td>
                                                <td>{item.severity_label || 'Unknown'}</td>
                                                <td>{item.severity_score || 'N/A'}</td>
                                                <td>{item.published_date}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                <div className="pagination-controls">
                                    <button 
                                        disabled={nvdPage === 1} 
                                        onClick={() => fetchNvdData(nvdPage - 1)}
                                    >
                                        ← Previous
                                    </button>
                                    <span>Page {nvdPage} of {Math.ceil(nvdTotal / 10)}</span>
                                    <button 
                                        disabled={nvdPage * 10 >= nvdTotal} 
                                        onClick={() => fetchNvdData(nvdPage + 1)}
                                    >
                                        Next →
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {activeTab === 'ic3' && (
                    <div className="tab-content">
                        <h2>IC3 - Internet Crime Complaints</h2>
                        <p>Coming soon...</p>
                    </div>
                )}
            </main>
        </div>
    );
};

export default Dashboard;