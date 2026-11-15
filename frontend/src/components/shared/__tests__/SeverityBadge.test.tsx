import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SeverityBadge from '../SeverityBadge';

describe('SeverityBadge', () => {
  it('renders High with dark text for contrast on orange', () => {
    render(<SeverityBadge label="High" />);
    expect(screen.getByText('High').style.color).toBe('rgb(26, 26, 26)');
  });

  it('renders Moderate with the Medium background and text colours', () => {
    render(<SeverityBadge label="Moderate" />);
    const el = screen.getByText('Moderate');
    expect(el.style.background).toBe('rgb(251, 192, 45)');
    expect(el.style.color).toBe('rgb(26, 26, 26)');
  });

  it('renders an inherited property name such as constructor as Unknown', () => {
    render(<SeverityBadge label="constructor" />);
    const el = screen.getByText('constructor');
    expect(el.style.background).toBe('rgb(158, 158, 158)');
    expect(el.style.color).toBe('rgb(26, 26, 26)');
  });

  it('renders Low with white text on the darker green', () => {
    render(<SeverityBadge label="Low" />);
    const el = screen.getByText('Low');
    expect(el.style.color).toBe('rgb(255, 255, 255)');
    expect(el.style.background).toBe('rgb(46, 125, 50)');
  });
});
