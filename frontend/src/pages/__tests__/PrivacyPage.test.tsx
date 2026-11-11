import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import PrivacyPage from '../PrivacyPage';

describe('PrivacyPage', () => {
  it('shows the Oregon region and the Gemini and domain-check providers', () => {
    render(
      <MemoryRouter>
        <PrivacyPage />
      </MemoryRouter>
    );

    expect(screen.getByText('US West (Oregon)')).toBeInTheDocument();
    expect(screen.queryByText(/Ohio/)).not.toBeInTheDocument();
    expect(screen.getByText('Google Gemini API')).toBeInTheDocument();
    expect(screen.getByText('HIBP, Shodan, AlienVault OTX, crt.sh')).toBeInTheDocument();
    expect(screen.getAllByText('Google global')).toHaveLength(3);
    expect(screen.getByText("Each provider's own")).toBeInTheDocument();
  });
});
