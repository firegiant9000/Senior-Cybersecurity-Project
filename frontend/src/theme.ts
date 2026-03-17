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
  Low:      '#388e3c',
  Unknown:  '#9e9e9e',
} as const

export const TILE_PALETTE = [
  COLORS.red,
  COLORS.blue,
  COLORS.tealDark,
  COLORS.navy,
  COLORS.redDark,
  COLORS.blueDark,
] as const
