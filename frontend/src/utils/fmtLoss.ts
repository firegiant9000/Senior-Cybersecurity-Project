/** Format a numeric loss value as a compact dollar string (e.g. "$12.5B"). */
export function fmtLoss(v: number | undefined): string {
    if (v === undefined) return '—';
    if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
    if (v >= 1_000_000)     return `$${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000)         return `$${Math.round(v / 1_000)}k`;
    return `$${v}`;
}
