import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const signedInUser = { uid: 'test-user' };
let mockUser: { uid: string } | null = null;

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}));

vi.mock('firebase/auth', () => ({
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}));

vi.mock('../../firebase', () => ({ auth: { currentUser: null } }));

import PrivacyPage from '../PrivacyPage';

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderPrivacy() {
  return render(
    <MemoryRouter initialEntries={['/privacy']}>
      <PrivacyPage />
      <LocationProbe />
    </MemoryRouter>
  );
}

describe('PrivacyPage', () => {
  beforeEach(() => {
    mockUser = null;
  });

  it('shows the Oregon region and the Gemini and domain-check providers', () => {
    renderPrivacy();

    expect(screen.getByText('US West (Oregon)')).toBeInTheDocument();
    expect(screen.queryByText(/Ohio/)).not.toBeInTheDocument();
    expect(screen.getByText('Google Gemini API')).toBeInTheDocument();
    expect(screen.getByText('HIBP, Shodan, AlienVault OTX, crt.sh')).toBeInTheDocument();
    expect(screen.getAllByText('Google global')).toHaveLength(3);
    expect(screen.getByText("Each provider's own")).toBeInTheDocument();
  });

  it('Back goes to the overview when signed in', () => {
    mockUser = signedInUser;
    renderPrivacy();

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));

    expect(screen.getByTestId('location').textContent).toBe('/overview');
  });

  it('Back goes to the landing page when signed out', () => {
    renderPrivacy();

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));

    expect(screen.getByTestId('location').textContent).toBe('/');
  });
});
