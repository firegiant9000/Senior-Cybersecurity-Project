import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SeverityBadge from '../SeverityBadge';

describe('SeverityBadge', () => {
  it('renders High with dark text for contrast on orange', () => {
    render(<SeverityBadge label="High" />);
    expect(screen.getByText('High').style.color).toBe('rgb(26, 26, 26)');
  });

  it('renders Moderate with the Medium text colour', () => {
    render(<SeverityBadge label="Moderate" />);
    expect(screen.getByText('Moderate').style.color).toBe('rgb(26, 26, 26)');
  });

  it('renders Low with white text on the darker green', () => {
    render(<SeverityBadge label="Low" />);
    const el = screen.getByText('Low');
    expect(el.style.color).toBe('rgb(255, 255, 255)');
    expect(el.style.background).toBe('rgb(46, 125, 50)');
  });
});
