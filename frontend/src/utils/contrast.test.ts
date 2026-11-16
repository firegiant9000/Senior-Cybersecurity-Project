import { describe, it, expect } from 'vitest';
import { contrastRatio } from './contrast';
import { DARK_CHIP_COLORS, SEVERITY_COLORS, SEVERITY_TEXT_COLORS, VIA_CHIP_COLORS } from '../theme';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Read from disk: vitest's CSS handling turns a `?raw` CSS import into an empty
// string, and under jsdom import.meta.url is not a file: URL.
// eslint-disable-next-line no-undef -- vitest injects __dirname; lint config has browser globals only
const dashboardCss = readFileSync(resolve(__dirname, '../Dashboard.css'), 'utf8');

/** `color-mix(in srgb, fg pct%, bg)` for #rrggbb inputs, as the chip renders it. */
function mix(fg: string, bg: string, pct: number): string {
  const ch = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
  return (
    '#' +
    [1, 3, 5]
      .map((i) => Math.round(ch(fg, i) * pct + ch(bg, i) * (1 - pct)).toString(16).padStart(2, '0'))
      .join('')
  );
}

describe('contrastRatio', () => {
  it('returns 21 for black on white', () => {
    expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21, 1);
  });

  it('returns 1 for identical colours', () => {
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 5);
  });

  it('is symmetric in argument order', () => {
    expect(contrastRatio('#1a1a1a', '#f57c00')).toBeCloseTo(contrastRatio('#f57c00', '#1a1a1a'), 10);
  });

  it('throws on a colour that is not #rrggbb', () => {
    expect(() => contrastRatio('#fff', '#000000')).toThrow();
  });
});

describe('severity badge text contrast', () => {
  it.each(Object.keys(SEVERITY_COLORS) as (keyof typeof SEVERITY_COLORS)[])(
    '%s text meets 4.5:1 against its background',
    (key) => {
      const ratio = contrastRatio(SEVERITY_TEXT_COLORS[key], SEVERITY_COLORS[key]);
      expect(ratio).toBeGreaterThanOrEqual(4.5);
    },
  );
});

describe('dark tier and confidence chip text contrast', () => {
  it.each(Object.keys(DARK_CHIP_COLORS) as (keyof typeof DARK_CHIP_COLORS)[])(
    '%s meets 4.5:1 on the dark card background',
    (key) => {
      expect(contrastRatio(DARK_CHIP_COLORS[key], '#22304a')).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(DARK_CHIP_COLORS[key], '#1e293b')).toBeGreaterThanOrEqual(4.5);
    },
  );
});

describe('discovered-via chip text contrast', () => {
  // The surfaces the chip actually sits on: the asset list table has no
  // background of its own, so it shows the page --bg; the detail modal is --card-bg.
  const backgrounds = {
    light: { page: '#f0f2f5', modal: '#ffffff' },
    dark: { page: '#111c33', modal: '#22304a' },
  } as const;

  for (const theme of ['light', 'dark'] as const) {
    it.each(Object.keys(VIA_CHIP_COLORS[theme]) as (keyof (typeof VIA_CHIP_COLORS)[typeof theme])[])(
      `${theme} %s meets 4.5:1 on the page and modal, plain and under its 12% tint`,
      (key) => {
        const fg = VIA_CHIP_COLORS[theme][key];
        for (const [surface, bg] of Object.entries(backgrounds[theme])) {
          expect(contrastRatio(fg, bg), `${surface} plain`).toBeGreaterThanOrEqual(4.5);
          expect(contrastRatio(fg, mix(fg, bg, 0.12)), `${surface} tinted`).toBeGreaterThanOrEqual(4.5);
        }
      },
    );
  }

  it('Dashboard.css --via-* tokens mirror VIA_CHIP_COLORS', () => {
    // The bare token blocks; other `[data-theme="dark"] .x {` rules don't match.
    const blocks = {
      light: dashboardCss.match(/:root\s*\{([^}]*)\}/)?.[1] ?? '',
      dark: dashboardCss.match(/\[data-theme="dark"\]\s*\{([^}]*)\}/)?.[1] ?? '',
    };
    for (const theme of ['light', 'dark'] as const) {
      for (const [key, hex] of Object.entries(VIA_CHIP_COLORS[theme])) {
        const match = blocks[theme].match(new RegExp(`--via-${key}:\\s*(#[0-9a-fA-F]{6})`));
        expect(match?.[1]?.toLowerCase(), `${theme} --via-${key}`).toBe(hex);
      }
    }
    // Exactly one light and one dark declaration each: no stray overrides elsewhere.
    for (const key of Object.keys(VIA_CHIP_COLORS.light)) {
      const count = dashboardCss.match(new RegExp(`--via-${key}:`, 'g'))?.length ?? 0;
      expect(count, `--via-${key} declarations`).toBe(2);
    }
  });
});
