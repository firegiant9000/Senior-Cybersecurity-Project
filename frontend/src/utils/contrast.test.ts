import { describe, it, expect } from 'vitest';
import { contrastRatio } from './contrast';
import { SEVERITY_COLORS, SEVERITY_TEXT_COLORS } from '../theme';

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
