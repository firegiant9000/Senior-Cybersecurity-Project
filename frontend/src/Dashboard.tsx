import React, { useState } from 'react';
import './Dashboard.css';
import SeverityDistributionChart from './components/SeverityDistributionChart';

interface EconomicsItem {
    id: number;
    state: string;
    smb_count: number | null | undefined;
    avg_revenue: number | null | undefined;
}

interface CISAVulnerability {
    id: string;
    vulnerability_name: string;
    vendor: string;
    product: string;
    severity_label: string;
    severity_score: number | null;
    risk_score: number | null;
    is_kev: boolean;
    kev_date_added: string;
    nvd_published?: string | null;
}

interface NVDCVEItem {
    id: string;
    description: string;
    severity_label: string;
    severity_score: number | null;
    published_date: string;
    last_modified: string;
}

interface IC3IncidentItem {
    id: number;
    year: number;
    sector: string;
    state: string;
    loss_amount: number | null | undefined;
}

interface ApiResponse<T> {
    total: number;
    page: number;
    page_size: number;
    items: T[];
}

const API_BASE_URL =
    (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
        .VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

const formatCurrencyCompact = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return 'N/A';
    const abs = Math.abs(value);
    if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
    if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `$${(value / 1e3).toFixed(2)}K`;
    return `$${value.toFixed(2)}`;
};

const STATE_NAME_BY_CODE: Record<string, string> = {
    AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
    CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia',
    HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa',
    KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland',
    MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri',
    MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey',
    NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio',
    OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina',
    SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
    VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
    DC: 'District of Columbia',
};

const expandStateName = (state: string): string => {
    const key = (state || '').trim().toUpperCase();
    return STATE_NAME_BY_CODE[key] ?? state;
};

const inferAttackType = (sector: string, lossAmount: number | null | undefined): string => {
    if (sector && sector.trim() && sector.trim().toLowerCase() !== 'all') {
        return sector;
    }
    const loss = lossAmount ?? 0;
    if (loss >= 150_000_000) return 'Business Email Compromise';
    if (loss >= 95_000_000) return 'Personal Data Breach';
    return 'Business Email Compromise';
};

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

interface IC3IncidentItem {
    id: number;
    year: number;
    attack_type: string;
    sector: string;
    state: string;
    complaint_count: number;
    loss_amount: number;
    avg_loss_per_incident: number;
}

interface ApiResponse<T> {
    total: number;
    page: number;
    page_size: number;
    items: T[];
}

const API_BASE_URL =
    (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
        .VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

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
    const [ic3Data, setIc3Data] = useState<IC3IncidentItem[]>([]);
    const [ic3Loading, setIc3Loading] = useState(false);
    const [ic3Error, setIc3Error] = useState<string | null>(null);
    const [ic3Page, setIc3Page] = useState(1);
    const [ic3Total, setIc3Total] = useState(0);

    useEffect(() => {
        if (activeTab === 'economics') {
            fetchEconomicsData(1);
        } else if (activeTab === 'cisa') {
            fetchCisaData(1);
        } else if (activeTab === 'nvd') {
            fetchNvdData(1);
        } else if (activeTab === 'ic3') {
            fetchIc3Data(1);
        }
    }, [activeTab]);

    const fetchEconomicsData = async (page: number) => {
        setEconomicsLoading(true);
        setEconomicsError(null);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/economics/indicators?page=${page}&page_size=10&sort_by=smb_count&sort_order=desc`);
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
            const response = await fetch(`${API_BASE_URL}/api/v1/vulnerabilities/exploited?page=${page}&page_size=10&sort_by=kev_date_added&sort_order=desc`);
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
            const url = `${API_BASE_URL}/api/v1/nvd/cves?page=${page}&page_size=10`;
            const response = await fetch(url);
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

    const fetchIc3Data = async (page: number) => {
        setIc3Loading(true);
        setIc3Error(null);
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/ic3/incidents?page=${page}&page_size=10&sort_by=loss_amount&sort_order=desc`);
            if (!response.ok) throw new Error(`Failed to fetch IC3 data: ${response.status}`);
            const data: ApiResponse<IC3IncidentItem> = await response.json();
            setIc3Data(data.items);
            setIc3Total(data.total);
            setIc3Page(page);
        } catch (err) {
            setIc3Error(err instanceof Error ? err.message : 'Error fetching IC3 data');
        } finally {
            setIc3Loading(false);
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
                    className={`tab ${activeTab === 'riskScoring' ? 'active' : ''}`}
                    onClick={() => setActiveTab('riskScoring')}
                >
                    Risk Scoring
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
                        <h2>State Economic Indicators</h2>
                        <div className="pagination-info">Showing {economicsData.length} of {economicsTotal} states</div>
                        {economicsLoading && <p>Loading economics data...</p>}
                        {economicsError && <p className="error">Error: {economicsError}</p>}
                        {economicsData.length > 0 && (
                            <>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>State</th>
                                            <th>Small Business Count</th>
                                            <th>Average Revenue</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {economicsData.map((item) => (
                                            <tr key={item.id}>
                                                <td>{expandStateName(item.state)}</td>
                                                <td>{item.smb_count?.toLocaleString() ?? 'N/A'}</td>
                                                <td>{formatCurrencyCompact(item.avg_revenue)}</td>
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

                {activeTab === 'riskScoring' && (
                    <div className="data-table-container">
                        <h2>Risk Scoring - NVD + KEV Combined ({riskTotal} total)</h2>
                        <div className="pagination-info">Showing {riskData.length} of {riskTotal} vulnerabilities with calculated risk scores</div>
                        {riskLoading && <p>Loading risk scoring data...</p>}
                        {riskError && <p className="error">Error: {riskError}</p>}
                        {riskData.length > 0 && (
                            <>
                                <div className="risk-analytics-grid">
                                    <div className="risk-analytics-card">
                                        <h3>Risk Distribution</h3>
                                        <div className="risk-bar-chart">
                                            {riskBands.map((band) => (
                                                <div className="risk-bar-row" key={band.label}>
                                                    <span className="risk-bar-label">{band.label}</span>
                                                    <div className="risk-bar-track">
                                                        <div
                                                            className="risk-bar-fill"
                                                            style={{
                                                                width: `${(band.count / maxBandCount) * 100}%`,
                                                                backgroundColor: band.color,
                                                            }}
                                                        />
                                                    </div>
                                                    <span className="risk-bar-value">{band.count}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="risk-analytics-card">
                                        <h3>Top Vendors by Avg Risk</h3>
                                        <div className="risk-bar-chart">
                                            {topVendorsByRisk.map((vendor) => (
                                                <div className="risk-bar-row" key={vendor.vendor}>
                                                    <span className="risk-bar-label">{vendor.vendor}</span>
                                                    <div className="risk-bar-track">
                                                        <div
                                                            className="risk-bar-fill risk-bar-fill-vendor"
                                                            style={{ width: `${(vendor.avgRisk / maxVendorRisk) * 100}%` }}
                                                        />
                                                    </div>
                                                    <span className="risk-bar-value">{vendor.avgRisk.toFixed(1)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="risk-kpi-card">
                                        <div className="risk-kpi-label">Average Risk (page)</div>
                                        <div className="risk-kpi-value">{avgRiskScore.toFixed(1)}</div>
                                        <div className="risk-kpi-subtitle">out of 100</div>
                                    </div>
                                </div>

                                <table className="data-table cisa-table">
                                    <thead>
                                        <tr>
                                            <th>CVE ID</th>
                                            <th>Data Source</th>
                                            <th>Vulnerability</th>
                                            <th>CVSS Score</th>
                                            <th>Risk Score</th>
                                            <th>Published</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {riskData.map((item) => (
                                            <tr key={item.id}>
                                                <td className="cve-id">
                                                    <a href={`https://nvd.nist.gov/vuln/detail/${item.id}`} target="_blank" rel="noopener noreferrer">
                                                        {item.id}
                                                    </a>
                                                </td>
                                                <td>
                                                    <span style={{
                                                        padding: '3px 8px',
                                                        borderRadius: '3px',
                                                        fontSize: '0.8em',
                                                        fontWeight: '600',
                                                        background: item.is_kev ? '#dc2626' : '#475569',
                                                        color: 'white'
                                                    }}>
                                                        {item.is_kev ? 'KEV' : 'NVD'}
                                                    </span>
                                                </td>
                                                <td className="vuln-name">{item.vulnerability_name.substring(0, 100)}...</td>
                                                <td>{item.severity_score ?? 'N/A'}</td>
                                                <td>
                                                    {item.risk_score !== null && item.risk_score !== undefined ? (
                                                        <span className="risk-badge" style={{
                                                            padding: '4px 8px',
                                                            borderRadius: '4px',
                                                            fontSize: '0.85em',
                                                            fontWeight: 'bold',
                                                            background: item.risk_score >= 80 ? '#7f1d1d' : item.risk_score >= 60 ? '#92400e' : item.risk_score >= 40 ? '#854d0e' : '#1e3a8a',
                                                            color: item.risk_score >= 80 ? '#fca5a5' : item.risk_score >= 60 ? '#fbbf24' : item.risk_score >= 40 ? '#fde047' : '#93c5fd',
                                                            border: `1px solid ${item.risk_score >= 80 ? '#991b1b' : item.risk_score >= 60 ? '#b45309' : item.risk_score >= 40 ? '#a16207' : '#1e40af'}`
                                                        }}>
                                                            {item.risk_score.toFixed(1)}/100
                                                        </span>
                                                    ) : 'N/A'}
                                                </td>
                                                <td>{item.nvd_published || 'N/A'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                <div className="pagination-controls">
                                    <button 
                                        disabled={riskPage === 1} 
                                        onClick={() => fetchRiskData(riskPage - 1)}
                                    >
                                        ← Previous
                                    </button>
                                    <span>Page {riskPage} of {Math.max(1, Math.ceil(riskTotal / 10))}</span>
                                    <button 
                                        disabled={riskPage >= Math.ceil(riskTotal / 10)}
                                        onClick={() => fetchRiskData(riskPage + 1)}
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
                                                <td className="cve-id">
                                                    <a href="https://www.cisa.gov/known-exploited-vulnerabilities-catalog" target="_blank" rel="noopener noreferrer">
                                                        {item.id}
                                                    </a>
                                                </td>
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
                        <SeverityDistributionChart />
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
