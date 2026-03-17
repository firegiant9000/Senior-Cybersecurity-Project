import React, { useMemo, useState } from 'react';
import {
    ComposableMap,
    Geographies,
    Geography,
    Annotation,
} from 'react-simple-maps';
import type { GeographicThreat } from '../api/dashboardSummary';

interface Props {
    data: GeographicThreat[];
    loading: boolean;
}

// FIPS numeric ID → 2-letter state abbreviation
const FIPS_TO_STATE: Record<string, string> = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA',
    '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL',
    '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN',
    '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME',
    '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS',
    '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
    '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
    '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
    '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
    '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI',
    '56': 'WY',
};

function interpolateTeal(ratio: number): string {
    // Low → light grey, High → deep teal (#006064)
    const r = Math.round(200 - ratio * 170);
    const g = Math.round(220 - ratio * 124);
    const b = Math.round(220 - ratio * 120);
    return `rgb(${r},${g},${b})`;
}

const GEO_URL = '/states-10m.json';

interface TooltipState {
    stateCode: string;
    stateName: string;
    complaints: number;
    x: number;
    y: number;
}

const CyberSecurityMap: React.FC<Props> = ({ data, loading }) => {
    const [tooltip, setTooltip] = useState<TooltipState | null>(null);

    const complaintByState = useMemo(() => {
        const map: Record<string, number> = {};
        for (const d of data) {
            map[d.state] = d.complaint_count;
        }
        return map;
    }, [data]);

    const maxComplaints = useMemo(
        () => Math.max(1, ...data.map(d => d.complaint_count)),
        [data]
    );

    if (loading) return <p style={{ color: '#888', fontSize: 13 }}>Loading…</p>;

    return (
        <div style={{ width: '100%', height: '100%', minHeight: 0, position: 'relative' }}>
            {/* Custom hover tooltip */}
            {tooltip && (
                <div style={{
                    position: 'absolute',
                    left: tooltip.x + 12,
                    top: tooltip.y - 10,
                    background: '#0b1060',
                    color: 'white',
                    padding: '6px 10px',
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    pointerEvents: 'none',
                    whiteSpace: 'nowrap',
                    zIndex: 10,
                    boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
                }}>
                    <div>{tooltip.stateName}</div>
                    <div style={{ color: '#00bcd4', marginTop: 2 }}>
                        {tooltip.complaints.toLocaleString()} complaints
                    </div>
                </div>
            )}
            <ComposableMap
                projection="geoAlbersUsa"
                style={{ width: '100%', height: '100%' }}
            >
                <Geographies geography={GEO_URL}>
                    {({ geographies }) =>
                        geographies.map((geo) => {
                            const fips = String(geo.id).padStart(2, '0');
                            const stateCode = FIPS_TO_STATE[fips];
                            const complaints = stateCode ? (complaintByState[stateCode] ?? 0) : 0;
                            const ratio = complaints / maxComplaints;
                            const fill = complaints > 0 ? interpolateTeal(ratio) : '#e8eaf0';

                            return (
                                <Geography
                                    key={geo.rsmKey}
                                    geography={geo}
                                    fill={fill}
                                    stroke="#ffffff"
                                    strokeWidth={0.5}
                                    style={{
                                        default: { outline: 'none' },
                                        hover:   { fill: '#00bcd4', outline: 'none', cursor: 'pointer' },
                                        pressed: { outline: 'none' },
                                    }}
                                    onMouseEnter={(e) => {
                                        const parentRect = (e.currentTarget as SVGElement)
                                            .closest('[style]')
                                            ?.getBoundingClientRect();
                                        setTooltip({
                                            stateCode: stateCode ?? String(geo.id),
                                            stateName: STATE_NAMES[stateCode ?? ''] ?? stateCode ?? String(geo.id),
                                            complaints,
                                            x: e.clientX - (parentRect?.left ?? 0),
                                            y: e.clientY - (parentRect?.top  ?? 0),
                                        });
                                    }}
                                    onMouseMove={(e) => {
                                        const parentRect = (e.currentTarget as SVGElement)
                                            .closest('[style]')
                                            ?.getBoundingClientRect();
                                        setTooltip(prev => prev ? {
                                            ...prev,
                                            x: e.clientX - (parentRect?.left ?? 0),
                                            y: e.clientY - (parentRect?.top  ?? 0),
                                        } : null);
                                    }}
                                    onMouseLeave={() => setTooltip(null)}
                                />
                            );
                        })
                    }
                </Geographies>

                {/* Highlight top 3 states with a marker label */}
                {data
                    .sort((a, b) => b.complaint_count - a.complaint_count)
                    .slice(0, 3)
                    .map((d) => {
                        const coords = STATE_LABEL_COORDS[d.state];
                        if (!coords) return null;
                        return (
                            <Annotation
                                key={d.state}
                                subject={coords}
                                dx={0}
                                dy={0}
                                connectorProps={{}}
                            >
                                <text
                                    textAnchor="middle"
                                    style={{ fontSize: 8, fontWeight: 700, fill: '#0b1060' }}
                                >
                                    {d.state}
                                </text>
                            </Annotation>
                        );
                    })}
            </ComposableMap>
        </div>
    );
};

// Full state names for the tooltip
const STATE_NAMES: Record<string, string> = {
    AL: 'Alabama',        AK: 'Alaska',         AZ: 'Arizona',        AR: 'Arkansas',
    CA: 'California',     CO: 'Colorado',        CT: 'Connecticut',    DE: 'Delaware',
    DC: 'Washington D.C.',FL: 'Florida',         GA: 'Georgia',        HI: 'Hawaii',
    ID: 'Idaho',          IL: 'Illinois',        IN: 'Indiana',        IA: 'Iowa',
    KS: 'Kansas',         KY: 'Kentucky',        LA: 'Louisiana',      ME: 'Maine',
    MD: 'Maryland',       MA: 'Massachusetts',   MI: 'Michigan',       MN: 'Minnesota',
    MS: 'Mississippi',    MO: 'Missouri',        MT: 'Montana',        NE: 'Nebraska',
    NV: 'Nevada',         NH: 'New Hampshire',   NJ: 'New Jersey',     NM: 'New Mexico',
    NY: 'New York',       NC: 'North Carolina',  ND: 'North Dakota',   OH: 'Ohio',
    OK: 'Oklahoma',       OR: 'Oregon',          PA: 'Pennsylvania',   RI: 'Rhode Island',
    SC: 'South Carolina', SD: 'South Dakota',    TN: 'Tennessee',      TX: 'Texas',
    UT: 'Utah',           VT: 'Vermont',         VA: 'Virginia',       WA: 'Washington',
    WV: 'West Virginia',  WI: 'Wisconsin',       WY: 'Wyoming',
};

// Approximate centroid coordinates [lon, lat] for labelling top states
const STATE_LABEL_COORDS: Record<string, [number, number]> = {
    AL: [-86.9, 32.8],  AK: [-153.4, 61.0], AZ: [-111.9, 34.0],
    AR: [-92.4, 34.9],  CA: [-119.4, 36.7], CO: [-105.5, 39.0],
    CT: [-72.7, 41.6],  DE: [-75.5, 39.0],  FL: [-81.5, 27.8],
    GA: [-83.4, 32.7],  HI: [-157.5, 20.3], ID: [-114.5, 44.4],
    IL: [-89.2, 40.3],  IN: [-86.1, 39.8],  IA: [-93.1, 41.9],
    KS: [-98.4, 38.5],  KY: [-85.3, 37.5],  LA: [-91.8, 31.2],
    ME: [-69.4, 45.3],  MD: [-77.0, 38.8],  MA: [-71.5, 42.3],
    MI: [-85.4, 44.3],  MN: [-94.3, 46.4],  MS: [-89.7, 32.7],
    MO: [-92.5, 38.5],  MT: [-110.4, 47.0], NE: [-99.9, 41.5],
    NV: [-116.4, 38.8], NH: [-71.6, 43.7],  NJ: [-74.4, 40.1],
    NM: [-106.1, 34.5], NY: [-75.5, 43.0],  NC: [-79.0, 35.5],
    ND: [-100.5, 47.5], OH: [-82.9, 40.4],  OK: [-97.5, 35.5],
    OR: [-120.5, 44.0], PA: [-77.2, 40.9],  RI: [-71.5, 41.7],
    SC: [-80.9, 33.8],  SD: [-100.2, 44.4], TN: [-86.7, 35.8],
    TX: [-99.3, 31.4],  UT: [-111.9, 39.3], VT: [-72.7, 44.0],
    VA: [-78.7, 37.5],  WA: [-120.5, 47.4], WV: [-80.6, 38.6],
    WI: [-89.6, 44.2],  WY: [-107.6, 43.0], DC: [-77.0, 38.9],
};

export default CyberSecurityMap;
