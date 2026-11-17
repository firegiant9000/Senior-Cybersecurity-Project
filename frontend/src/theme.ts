/** Single source of truth for all design tokens used across the dashboard. */

export const COLORS = {
  navy:        '#0b1060',
  navyLight:   '#1a2080',
  teal:        '#00bcd4',
  tealDark:    '#00838f',
  red:         '#d32f2f',
  redDark:     '#c62828',
  blue:        '#1565c0',
  blueDark:    '#0d47a1',
  purple:      '#3f51b5',
  green:       '#2e7d32',
  bg:          '#f0f2f5',
  cardBg:      '#ffffff',
  border:      '#e5e7eb',
  textPrimary: '#111827',
  textMuted:   '#6b7280',
  textLight:   'rgba(255,255,255,0.75)',
} as const

export const RISK_COLORS = {
  Critical: COLORS.red,
  High:     COLORS.navy,
  Medium:   COLORS.teal,
  Low:      COLORS.green,
  Unknown:  '#9e9e9e',
} as const

/**
 * Conventional security-industry severity colours (red → orange → yellow → green).
 * Use these for CVE/KEV severity badges and chart fills.
 * Distinct from RISK_COLORS which uses the dashboard's navy/teal palette.
 */
export const SEVERITY_COLORS = {
  Critical: '#d32f2f',
  High:     '#f57c00',
  Medium:   '#fbc02d',
  Low:      '#2e7d32',
  Unknown:  '#9e9e9e',
} as const

/** Map any severity label (case-insensitive; 'Moderate' = Medium) to a SEVERITY_COLORS key. */
export function normalizeSeverity(label: string | null | undefined): keyof typeof SEVERITY_COLORS {
  const s = (label ?? '').trim().toLowerCase()
  if (s === 'moderate') return 'Medium'
  for (const key of Object.keys(SEVERITY_COLORS) as (keyof typeof SEVERITY_COLORS)[]) {
    if (key.toLowerCase() === s) return key
  }
  return 'Unknown'
}

/** Chart/badge fill for a raw data severity label. */
export function severityColor(label: string | null | undefined): string {
  return SEVERITY_COLORS[normalizeSeverity(label)]
}

/** Badge text colours chosen to meet WCAG 4.5:1 against SEVERITY_COLORS. */
export const SEVERITY_TEXT_COLORS = {
  Critical: '#ffffff',
  High:     '#1a1a1a',
  Medium:   '#1a1a1a',
  Low:      '#ffffff',
  Unknown:  '#1a1a1a',
} as const

/**
 * Light-theme text colours for the AssetsPage tier and confidence chips.
 * MIRRORED in the `:root` block of Dashboard.css (--tier-* and --conf-*);
 * keep both in sync. contrast.test.ts asserts each is at least 4.5:1 on the
 * page background (asset list) and the card background (detail modal), both
 * plain and under the chip's 12% colour-mix tint.
 */
export const LIGHT_CHIP_COLORS = {
  'tier-critical': '#991b1b',
  'tier-high':     '#9a3412',
  'tier-medium':   '#92400e',
  'tier-low':      '#166534',
  'tier-review':   '#475569',
  'conf-high':     '#166534',
  'conf-medium':   '#92400e',
  'conf-low':      '#475569',
} as const

/**
 * Dark-theme text colours for the AssetsPage tier and confidence chips.
 * MIRRORED in the `[data-theme="dark"]` block of Dashboard.css
 * (--tier-* and --conf-*); keep both in sync. contrast.test.ts asserts each
 * is at least 4.5:1 on the page and card backgrounds, plain and tinted.
 */
export const DARK_CHIP_COLORS = {
  'tier-critical': '#fca5a5',
  'tier-high':     '#fdba74',
  'tier-medium':   '#fcd34d',
  'tier-low':      '#86efac',
  'tier-review':   '#cbd5e1',
  'conf-high':     '#86efac',
  'conf-medium':   '#fcd34d',
  'conf-low':      '#cbd5e1',
} as const

/**
 * Text colours for the AssetsPage "discovered via" chip (CSV / M365 / Agent).
 * MIRRORED as --via-* in Dashboard.css (:root = light, [data-theme="dark"] =
 * dark); keep both in sync. contrast.test.ts asserts each is at least 4.5:1 on
 * the page background (asset list) and the card background (detail modal),
 * both plain and under the chip's 12% colour-mix tint.
 */
export const VIA_CHIP_COLORS = {
  light: { csv: '#1d4ed8', m365: '#7e22ce', agent: '#065f46', other: '#475569' },
  dark:  { csv: '#93c5fd', m365: '#d8b4fe', agent: '#6ee7b7', other: '#cbd5e1' },
} as const

export const TILE_PALETTE = [
  COLORS.red,
  COLORS.blue,
  COLORS.tealDark,
  COLORS.navy,
  COLORS.redDark,
  COLORS.blueDark,
] as const
