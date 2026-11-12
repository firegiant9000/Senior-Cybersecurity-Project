export function fmtMoney(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${Math.round(v / 1_000)}k`;
  return `$${v}`;
}

export function truncate(str: string, max = 22): string {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

export const TOOLTIP_CONTENT_STYLE = {
  backgroundColor: 'var(--card-bg)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  fontSize: 12,
  borderRadius: 6,
} as const;
export const TOOLTIP_ITEM_STYLE = { color: 'var(--text-primary)' } as const;
export const TOOLTIP_LABEL_STYLE = { color: 'var(--text-primary)', fontWeight: 600 } as const;
