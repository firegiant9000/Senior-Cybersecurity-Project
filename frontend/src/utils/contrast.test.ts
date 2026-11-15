import { describe, it, expect } from 'vitest';
import { contrastRatio } from './contrast';
import { DARK_CHIP_COLORS, SEVERITY_COLORS, SEVERITY_TEXT_COLORS } from '../theme';

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
