import React, { useState, useEffect } from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from 'recharts';

interface SeverityCount {
    severity: string;
    count: number;
}

interface SeverityDistributionData {
    items: SeverityCount[];
    total_cves: number;
    date_from: string | null;
    date_to: string | null;
}

const SEVERITY_COLORS: Record<string, string> = {
    Critical: '#d32f2f',
    High: '#f57c00',
    Medium: '#fbc02d',
    Low: '#388e3c',
    Unknown: '#9e9e9e',
};

const API_BASE_URL =
    (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
        .VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

const SeverityDistributionChart: React.FC = () => {
    const [data, setData] = useState<SeverityCount[]>([]);
    const [totalCves, setTotalCves] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/v1/nvd/analytics/severity-distribution`
                );
                if (!response.ok) {
                    throw new Error(`Failed to fetch severity data: ${response.status}`);
                }
                const result: SeverityDistributionData = await response.json();
                setData(result.items);
                setTotalCves(result.total_cves);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Error fetching severity data');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <p>Loading severity distribution...</p>;
    if (error) return <p className="error">Error: {error}</p>;
    if (data.length === 0) return <p>No severity data available.</p>;

    return (
        <div className="severity-chart-container">
            <h3>CVE Severity Distribution</h3>
            <p className="severity-chart-total">Total CVEs: {totalCves.toLocaleString()}</p>
            <ResponsiveContainer width="100%" height={320}>
                <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="severity" />
                    <YAxis allowDecimals={false} />
                    <Tooltip
                        formatter={(value) => [Number(value).toLocaleString(), 'CVEs']}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                        {data.map((entry) => (
                            <Cell
                                key={entry.severity}
                                fill={SEVERITY_COLORS[entry.severity] || '#9e9e9e'}
                            />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default SeverityDistributionChart;
