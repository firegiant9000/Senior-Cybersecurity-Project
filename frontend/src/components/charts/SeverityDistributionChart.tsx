import React, { useState, useEffect } from 'react';
import { SEVERITY_COLORS } from '../../theme';
import { fetchWithAuth } from '../../api/fetchWithAuth';
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


interface Props {
    apiBaseUrl: string;
    search?: string;
    severity?: string;
}

const SeverityDistributionChart: React.FC<Props> = ({ apiBaseUrl, search, severity }) => {
    const [data, setData] = useState<SeverityCount[]>([]);
    const [totalCves, setTotalCves] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const controller = new AbortController();
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const params = new URLSearchParams();
                if (search) params.set('search', search);
                if (severity) params.set('severity', severity);
                const qs = params.toString();
                const response = await fetchWithAuth(
                    `${apiBaseUrl}/api/v1/nvd/analytics/severity-distribution${qs ? `?${qs}` : ''}`,
                    { signal: controller.signal }
                );
                if (!response.ok) {
                    throw new Error(`Failed to fetch severity data: ${response.status}`);
                }
                const result: SeverityDistributionData = await response.json();
                setData(result.items);
                setTotalCves(result.total_cves);
            } catch (err) {
                if (err instanceof DOMException && err.name === 'AbortError') return;
                setError(err instanceof Error ? err.message : 'Error fetching severity data');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
        return () => controller.abort();
    }, [apiBaseUrl, search, severity]);

    if (loading) return <p>Loading severity distribution...</p>;
    if (error) return <p className="error">Error: {error}</p>;
    if (data.length === 0) return <p>No severity data available.</p>;

    return (
        <div className="severity-chart-container">
            <h3>CVE Severity Distribution</h3>
            <p className="severity-chart-total">Total CVEs: {totalCves.toLocaleString()}</p>
            <div className="chart-aspect-box">
                <ResponsiveContainer width="100%" height="100%">
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
                                    fill={SEVERITY_COLORS[entry.severity as keyof typeof SEVERITY_COLORS] ?? '#9e9e9e'}
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default SeverityDistributionChart;
