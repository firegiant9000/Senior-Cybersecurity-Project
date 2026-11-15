/** WCAG 2.x relative luminance of a `#rrggbb` colour. */
const HEX_COLOUR = /^#[0-9a-f]{6}$/i;

function relativeLuminance(hex: string): number {
  if (!HEX_COLOUR.test(hex)) {
    throw new Error(`contrastRatio expects #rrggbb colours, got "${hex}"`);
  }
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4),
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio (1 to 21) between two `#rrggbb` colours. */
export function contrastRatio(fg: string, bg: string): number {
  const a = relativeLuminance(fg);
  const b = relativeLuminance(bg);
  const [lighter, darker] = a >= b ? [a, b] : [b, a];
  return (lighter + 0.05) / (darker + 0.05);
}
