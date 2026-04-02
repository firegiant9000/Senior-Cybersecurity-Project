import type {
  AttackTypeStats,
  GeographicThreat,
  SectorAttackCombination,
} from "../api/dashboardSummary";

/** Map full state name or code to two-letter code (aligns with CyberSecurityMap). */
const STATE_NAME_TO_CODE: Record<string, string> = {
  Alabama: "AL",
  Alaska: "AK",
  Arizona: "AZ",
  Arkansas: "AR",
  California: "CA",
  Colorado: "CO",
  Connecticut: "CT",
  Delaware: "DE",
  Florida: "FL",
  Georgia: "GA",
  Hawaii: "HI",
  Idaho: "ID",
  Illinois: "IL",
  Indiana: "IN",
  Iowa: "IA",
  Kansas: "KS",
  Kentucky: "KY",
  Louisiana: "LA",
  Maine: "ME",
  Maryland: "MD",
  Massachusetts: "MA",
  Michigan: "MI",
  Minnesota: "MN",
  Mississippi: "MS",
  Missouri: "MO",
  Montana: "MT",
  Nebraska: "NE",
  Nevada: "NV",
  "New Hampshire": "NH",
  "New Jersey": "NJ",
  "New Mexico": "NM",
  "New York": "NY",
  "North Carolina": "NC",
  "North Dakota": "ND",
  Ohio: "OH",
  Oklahoma: "OK",
  Oregon: "OR",
  Pennsylvania: "PA",
  "Rhode Island": "RI",
  "South Carolina": "SC",
  "South Dakota": "SD",
  Tennessee: "TN",
  Texas: "TX",
  Utah: "UT",
  Vermont: "VT",
  Virginia: "VA",
  Washington: "WA",
  "West Virginia": "WV",
  Wisconsin: "WI",
  Wyoming: "WY",
};

export function normalizeStateCode(state: string | null | undefined): string | null {
  if (!state?.trim()) return null;
  const s = state.trim();
  if (s.length === 2) return s.toUpperCase();
  return STATE_NAME_TO_CODE[s] ?? null;
}

const INDUSTRY_TO_IC3_SECTOR: Record<string, string> = {
  "Finance & Insurance": "Finance",
  Healthcare: "Healthcare",
  "Tech & Software": "Technology",
  Government: "Government",
  "Retail & E-Commerce": "Retail",
  Education: "Education",
  Manufacturing: "Manufacturing",
  "Professional Services": "Professional Services",
  Other: "Technology",
};

export function resolveSectorFromIndustry(industry: string | null | undefined): string | null {
  if (!industry?.trim()) return null;
  return INDUSTRY_TO_IC3_SECTOR[industry] ?? industry;
}

export function getGeographicRow(
  threats: GeographicThreat[],
  stateCode: string | null,
): GeographicThreat | null {
  if (!stateCode) return null;
  for (const row of threats) {
    const code = normalizeStateCode(row.state);
    if (code === stateCode) return row;
  }
  return null;
}

export function aggregateAttackTypesForSector(
  matrix: SectorAttackCombination[],
  sector: string,
): AttackTypeStats[] {
  const agg = new Map<string, { complaint_count: number; total_loss: number }>();
  for (const row of matrix) {
    if (row.sector !== sector) continue;
    const cur = agg.get(row.attack_type) ?? { complaint_count: 0, total_loss: 0 };
    cur.complaint_count += row.complaint_count;
    cur.total_loss += row.total_loss;
    agg.set(row.attack_type, cur);
  }
  return [...agg.entries()].map(([attack_type, v]) => ({
    attack_type,
    complaint_count: v.complaint_count,
    total_loss: v.total_loss,
    avg_loss: v.complaint_count > 0 ? v.total_loss / v.complaint_count : 0,
  }));
}

export function filterMatrixBySector(
  matrix: SectorAttackCombination[],
  sector: string,
): SectorAttackCombination[] {
  return matrix.filter((r) => r.sector === sector);
}

export interface RiskScoreFactor {
  label: string;
  detail: string;
  contribution: number;
}

export interface PersonalRiskScoreResult {
  score: number;
  factors: RiskScoreFactor[];
}

/** 0–100 composite score from regional, industry, and exploitation signals (demo heuristic). */
export function computePersonalRiskScore(params: {
  geographicThreats: GeographicThreat[];
  sectorAttackMatrix: SectorAttackCombination[];
  userStateCode: string | null;
  userSector: string | null;
  pctExploited: number | null;
}): PersonalRiskScoreResult {
  const { geographicThreats, sectorAttackMatrix, userStateCode, userSector, pctExploited } =
    params;

  const maxStateComplaints = Math.max(
    1,
    ...geographicThreats.map((g) => g.complaint_count),
  );

  const stateRow = getGeographicRow(geographicThreats, userStateCode);
  const regionalRatio = stateRow
    ? Math.min(1, stateRow.complaint_count / maxStateComplaints)
    : 0.5;
  const regionalScore = regionalRatio * 100;

  const sectorTotals: Record<string, number> = {};
  for (const row of sectorAttackMatrix) {
    sectorTotals[row.sector] = (sectorTotals[row.sector] ?? 0) + row.complaint_count;
  }
  const maxSector = Math.max(1, ...Object.values(sectorTotals));
  const mySectorTotal = userSector ? (sectorTotals[userSector] ?? 0) : 0;
  const industryRatio = userSector ? Math.min(1, mySectorTotal / maxSector) : 0.5;
  const industryScore = industryRatio * 100;

  const kevPct = pctExploited ?? 0;
  const landscapeScore = Math.min(100, kevPct * 2.5);

  const wReg = 0.3;
  const wInd = 0.35;
  const wLands = 0.35;

  const score = Math.round(
    wReg * regionalScore + wInd * industryScore + wLands * landscapeScore,
  );
  const clamped = Math.max(0, Math.min(100, score));

  return {
    score: clamped,
    factors: [
      {
        label: "Regional exposure",
        detail: userStateCode
          ? `${stateRow?.complaint_count.toLocaleString() ?? "—"} complaints in your state vs peak US state`
          : "Add your state in organization settings",
        contribution: Math.round(wReg * regionalScore),
      },
      {
        label: "Industry targeting",
        detail: userSector
          ? `${mySectorTotal.toLocaleString()} complaints recorded in ${userSector}`
          : "Industry not set",
        contribution: Math.round(wInd * industryScore),
      },
      {
        label: "Active exploitation landscape",
        detail:
          pctExploited !== null
            ? `${pctExploited.toFixed(1)}% of tracked CVEs appear on CISA KEV`
            : "CVE / KEV data unavailable",
        contribution: Math.round(wLands * landscapeScore),
      },
    ],
  };
}

export function riskScoreColor(score: number): string {
  if (score < 30) return "#2e7d32";
  if (score <= 60) return "#f9a825";
  return "#c62828";
}
