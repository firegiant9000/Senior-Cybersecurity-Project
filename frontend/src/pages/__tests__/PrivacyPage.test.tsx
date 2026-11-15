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

  it('describes export and deletion as requests to the site operator', () => {
    renderPrivacy();

    expect(
      screen.getByText(
        /an organisation admin can ask the site operator for a JSON file of your organisation's data: its profile, domains, vendors, assets and installed software, .* It does not include login accounts, audit records, per-asset vulnerability matches or integration tokens\./,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /an organisation admin can ask the site operator to permanently delete the organisation and that same data\. Member login accounts are not deleted; they are detached from the organisation\. Audit records are kept, including a record of the deletion itself, for the retention period under Activity above\./,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/asks for their own account to be deleted/i)).toBeNull();
    expect(screen.queryByText(/everything we hold/)).toBeNull();
    expect(
      screen.getByText(
        'To make either request, contact the site operator from the account that administers your organisation.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Correct:')).toBeInTheDocument();
  });

  it('says what the logged-out readiness check keeps and what it does not', () => {
    renderPrivacy();

    expect(screen.getByRole('heading', { name: 'The readiness check (no login)' })).toBeInTheDocument();
    expect(screen.getByText(/the quiz is not available yet\./)).toBeInTheDocument();
    expect(screen.getByText(/is looked up in public DNS .* and is not saved or logged\./)).toBeInTheDocument();
    expect(screen.getByText(/reuses the result for up to 15 minutes/)).toBeInTheDocument();
    expect(screen.getByText(/It is not sent to the domain-check providers listed below\./)).toBeInTheDocument();
    expect(screen.getByText(/request logs \(which include your IP address or a proxy's\)/)).toBeInTheDocument();
    expect(screen.getByText(/are scored and shown back to you\. They are not stored or logged\./)).toBeInTheDocument();
    expect(screen.getByText(/with no visitor ID, IP address, domain or answer attached\./)).toBeInTheDocument();
    expect(screen.getByText(/appears in the server's request logs and is used for rate limiting\./)).toBeInTheDocument();
    expect(screen.queryByText(/anonymized request logs/)).toBeNull();
  });

  it('shows no API endpoints in the rights section', () => {
    renderPrivacy();

    expect(screen.queryByText(/\/api\/v1\//)).toBeNull();
    expect(screen.queryByText(/GET \/api|DELETE \/api/)).toBeNull();
  });
});
