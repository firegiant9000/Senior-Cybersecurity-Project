import React, { useMemo, useRef, useState } from 'react';
import {
    ComposableMap,
    Geographies,
    Geography,
    Annotation,
} from 'react-simple-maps';
import type { GeographicThreat } from '../../api/dashboardSummary';

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

const GEO_URL = '/states-10m.json';

const STATE_NAME_TO_CODE: Record<string, string> = {
    Alabama: 'AL', Alaska: 'AK', Arizona: 'AZ', Arkansas: 'AR', California: 'CA',
    Colorado: 'CO', Connecticut: 'CT', Delaware: 'DE', Florida: 'FL', Georgia: 'GA',
    Hawaii: 'HI', Idaho: 'ID', Illinois: 'IL', Indiana: 'IN', Iowa: 'IA',
    Kansas: 'KS', Kentucky: 'KY', Louisiana: 'LA', Maine: 'ME', Maryland: 'MD',
    Massachusetts: 'MA', Michigan: 'MI', Minnesota: 'MN', Mississippi: 'MS', Missouri: 'MO',
    Montana: 'MT', Nebraska: 'NE', Nevada: 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND',
    Ohio: 'OH', Oklahoma: 'OK', Oregon: 'OR', Pennsylvania: 'PA', 'Rhode Island': 'RI',
    'South Carolina': 'SC', 'South Dakota': 'SD', Tennessee: 'TN', Texas: 'TX',
    Utah: 'UT', Vermont: 'VT', Virginia: 'VA', Washington: 'WA', 'West Virginia': 'WV',
    Wisconsin: 'WI', Wyoming: 'WY',
    'Washington DC': 'DC', 'Washington D.C.': 'DC', 'District of Columbia': 'DC',
};

function toStateCode(state: string): string | null {
    const s = state.trim();
    if (!s) return null;
    const upper = s.toUpperCase();
    if (STATE_NAMES[upper]) return upper;
    return STATE_NAME_TO_CODE[s] ?? null;
}

function interpolateTeal(ratio: number): string {
    // Low → light grey, High → deep teal (#006064)
    const r = Math.round(200 - ratio * 170);
    const g = Math.round(220 - ratio * 124);
    const b = Math.round(220 - ratio * 120);
    return `rgb(${r},${g},${b})`;
}

interface TooltipState {
    stateCode: string;
    stateName: string;
    complaints: number;
    totalLoss: number;
    avgLoss: number;
    x: number;
    y: number;
}

function fmtLossShort(v: number): string {
    if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
    if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `$${Math.round(v / 1_000)}k`;
    return `$${v.toLocaleString()}`;
}

const CyberSecurityMap: React.FC<Props> = ({ data, loading }) => {
    const [tooltip, setTooltip] = useState<TooltipState | null>(null);
    const mapContainerRef = useRef<HTMLDivElement | null>(null);

    const complaintByState = useMemo(() => {
        const map: Record<string, number> = {};
        for (const d of data) {
            const stateCode = toStateCode(d.state);
            if (!stateCode) continue;
            map[stateCode] = (map[stateCode] ?? 0) + d.complaint_count;
        }
        return map;
    }, [data]);

    const totalLossByState = useMemo(() => {
        const map: Record<string, number> = {};
        for (const d of data) {
            const stateCode = toStateCode(d.state);
            if (!stateCode) continue;
            map[stateCode] = (map[stateCode] ?? 0) + d.total_loss;
        }
        return map;
    }, [data]);

    const maxComplaints = useMemo(
        () => Math.max(1, ...Object.values(complaintByState)),
        [complaintByState]
    );

    const minComplaints = useMemo(() => {
        const vals = Object.values(complaintByState).filter(v => v > 0);
        return vals.length > 0 ? Math.min(...vals) : 0;
    }, [complaintByState]);

    const topStateCodes = useMemo(
        () => Object.entries(complaintByState)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
            .map(([stateCode]) => stateCode),
        [complaintByState]
    );

    if (loading) return <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>Loading…</p>;

    const ariaLabel = topStateCodes.length > 0
        ? `US map of FBI IC3 cybercrime complaints by state. Top states: ${topStateCodes.map(c => `${STATE_NAMES[c] ?? c} (${(complaintByState[c] ?? 0).toLocaleString()} complaints)`).join(', ')}.`
        : 'US map of FBI IC3 cybercrime complaints by state.';

    return (
        <div style={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <div ref={mapContainerRef} style={{ flex: 1, position: 'relative', minHeight: 0 }} role="img" aria-label={ariaLabel}>
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
                    {tooltip.totalLoss > 0 && (
                        <>
                            <div style={{ color: '#b2ebf2', marginTop: 1 }}>
                                {fmtLossShort(tooltip.totalLoss)} total losses
                            </div>
                            <div style={{ color: '#b2ebf2' }}>
                                {fmtLossShort(tooltip.avgLoss)} avg per incident
                            </div>
                        </>
                    )}
                </div>
            )}
            <ComposableMap
                projection="geoAlbersUsa"
                style={{ width: '100%', height: '100%' }}
                aria-hidden="true"
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
                                        const parentRect = mapContainerRef.current?.getBoundingClientRect();
                                        const loss = stateCode ? (totalLossByState[stateCode] ?? 0) : 0;
                                        setTooltip({
                                            stateCode: stateCode ?? String(geo.id),
                                            stateName: STATE_NAMES[stateCode ?? ''] ?? stateCode ?? String(geo.id),
                                            complaints,
                                            totalLoss: loss,
                                            avgLoss: complaints > 0 ? loss / complaints : 0,
                                            x: e.clientX - (parentRect?.left ?? 0),
                                            y: e.clientY - (parentRect?.top  ?? 0),
                                        });
                                    }}
                                    onMouseMove={(e) => {
                                        const parentRect = mapContainerRef.current?.getBoundingClientRect();
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
                {topStateCodes
                    .map((stateCode) => {
                        const coords = STATE_LABEL_COORDS[stateCode];
                        if (!coords) return null;
                        return (
                            <Annotation
                                key={stateCode}
                                subject={coords}
                                dx={0}
                                dy={0}
                                connectorProps={{}}
                            >
                                <text
                                    textAnchor="middle"
                                    style={{ fontSize: 8, fontWeight: 700, fill: '#0b1060' }}
                                >
                                    {stateCode}
                                </text>
                            </Annotation>
                        );
                    })}
            </ComposableMap>
            </div>
            {/* Legend — built from the same color function the map uses */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 4px 2px', flexShrink: 0 }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted, #6b7280)', whiteSpace: 'nowrap' }}>
                    {minComplaints.toLocaleString()}
                </span>
                <div style={{
                    flex: 1,
                    height: 8,
                    borderRadius: 4,
                    background: `linear-gradient(to right, #e8eaf0 0%, #e8eaf0 4%, ${interpolateTeal(0)} 4%, ${interpolateTeal(0.25)} 28%, ${interpolateTeal(0.5)} 52%, ${interpolateTeal(0.75)} 76%, ${interpolateTeal(1)} 100%)`,
                }} />
                <span style={{ fontSize: 10, color: 'var(--text-muted, #6b7280)', whiteSpace: 'nowrap' }}>
                    {maxComplaints.toLocaleString()}
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-muted, #6b7280)', marginLeft: 6, whiteSpace: 'nowrap' }}>
                    Complaints reported (FBI IC3)
                </span>
            </div>
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
