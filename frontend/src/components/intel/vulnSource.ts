export type VulnSource = 'scored' | 'kev' | 'nvd';

export function parseVulnSource(value: string | null): VulnSource {
  return value === 'kev' || value === 'nvd' || value === 'scored' ? value : 'scored';
}

export const RISK_SCORE_TIP =
  '0–100 composite combining CVSS severity, KEV presence, EPSS exploitation probability, and recency. Higher = more risk.';

export const SEVERITY_ORDER = ['Critical', 'High', 'Medium', 'Low', 'Unknown'];

export const BAND_COLORS: Record<string, string> = {
  'Critical (80-100)': '#dc2626',
  'High (60-79)': '#f59e0b',
  'Medium (40-59)': '#eab308',
  'Low (0-39)': '#3b82f6',
};

export function fmtM(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)     return `${Math.round(v / 1_000)}k`;
  return String(v);
}
