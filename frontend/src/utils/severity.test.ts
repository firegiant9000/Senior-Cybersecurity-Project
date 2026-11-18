import { describe, it, expect } from 'vitest';
import { normalizeSeverity, severityColor } from '../theme';

describe('normalizeSeverity', () => {
  it('maps Moderate to Medium, case-insensitively', () => {
    expect(normalizeSeverity('Moderate')).toBe('Medium');
    expect(normalizeSeverity('moderate')).toBe('Medium');
  });

  it('is case-insensitive for known labels', () => {
    expect(normalizeSeverity('CRITICAL')).toBe('Critical');
    expect(normalizeSeverity('high')).toBe('High');
    expect(normalizeSeverity(' Low ')).toBe('Low');
  });

  it('falls back to Unknown', () => {
    expect(normalizeSeverity('bogus')).toBe('Unknown');
    expect(normalizeSeverity('')).toBe('Unknown');
    expect(normalizeSeverity(null)).toBe('Unknown');
    expect(normalizeSeverity(undefined)).toBe('Unknown');
    expect(normalizeSeverity('constructor')).toBe('Unknown');
  });
});

describe('severityColor', () => {
  it('renders Moderate as the Medium yellow', () => {
    expect(severityColor('Moderate')).toBe('#fbc02d');
  });

  it('renders unknown labels grey', () => {
    expect(severityColor('nope')).toBe('#9e9e9e');
  });
});
