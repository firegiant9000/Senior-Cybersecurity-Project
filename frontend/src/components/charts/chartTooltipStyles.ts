/**
 * Shared Recharts tooltip / cursor styling.
 *
 * Recharts defaults to a white tooltip with near-black text — fine in light
 * mode but unreadable on the dark theme. Wiring CSS variables in here lets
 * each chart inherit the dashboard tokens without duplicating the same
 * inline-style object across files.
 */

import type { CSSProperties } from 'react';

export const TOOLTIP_CONTENT_STYLE: CSSProperties = {
  backgroundColor: 'var(--card-bg)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  fontSize: 12,
  borderRadius: 6,
};

export const TOOLTIP_ITEM_STYLE: CSSProperties = {
  color: 'var(--text-primary)',
};

export const TOOLTIP_LABEL_STYLE: CSSProperties = {
  color: 'var(--text-primary)',
  fontWeight: 600,
};

// Subtle blue tint behind the hovered bar, matching the activeBar stroke
// already used in MalwareBarChart / IncidentManagementChart.
export const TOOLTIP_CURSOR = { fill: 'rgba(59, 130, 246, 0.08)' };

// Axis tick fill — picks up --text-muted so labels stay readable in both
// dark and light themes.
export const AXIS_TICK_STYLE = { fontSize: 12, fill: 'var(--text-muted)' };
