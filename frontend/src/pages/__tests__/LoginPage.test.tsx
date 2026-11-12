import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockNavigate = vi.fn();
const mockLogin = vi.fn();
const mockSignup = vi.fn();
let mockUser: { uid: string } | null = null;
let mockLoading = false;

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading, login: mockLogin, signup: mockSignup }),
}));

vi.mock('firebase/auth', () => ({
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}));

vi.mock('../../firebase', () => ({ auth: { currentUser: null } }));

import LoginPage from '../LoginPage';

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="search">{location.search}</div>;
}

function renderAt(url: string, defaultSignUp = false) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <LocationProbe />
      <Routes>
        <Route path="/login" element={<LoginPage defaultSignUp={defaultSignUp} />} />
        <Route path="/signup" element={<LoginPage defaultSignUp={defaultSignUp} />} />
        <Route path="/dashboard" element={<div>DASHBOARD ROUTE</div>} />
        <Route path="/invites/:token" element={<div>INVITE ROUTE</div>} />
      </Routes>
    </MemoryRouter>
  );
}

function fillAndSubmitSignIn() {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.co' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret12' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));
}

describe('LoginPage next handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = null;
    mockLoading = false;
    mockLogin.mockResolvedValue(undefined);
    mockSignup.mockResolvedValue(undefined);
  });

  it('signs in and navigates to next', async () => {
    renderAt('/login?next=/invites/tok');
    fillAndSubmitSignIn();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/invites/tok'));
    expect(mockNavigate).toHaveBeenCalledTimes(1);
  });

  it.each([
    '/login?next=//evil.example',
    '/login?next=/\\evil.example',
    '/login?next=https://evil.example',
    '/login?next=%2F%2Fevil.example',
  ])('falls back to the dashboard for an unsafe next (%j)', async (url) => {
    renderAt(url);
    fillAndSubmitSignIn();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/dashboard'));
    expect(mockNavigate).toHaveBeenCalledTimes(1);
  });

  it('sign-up uses the same destination', async () => {
    renderAt('/signup?next=/invites/tok', true);
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret12' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'secret12' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/invites/tok'));
    expect(mockSignup).toHaveBeenCalledWith('a@b.co', 'secret12');
  });

  it('a signed-in user is redirected', () => {
    mockUser = { uid: 'u1' };
    renderAt('/login?next=/invites/tok');
    expect(screen.getByText('INVITE ROUTE')).toBeInTheDocument();
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('a signed-in user with an unsafe next is redirected to the dashboard', () => {
    mockUser = { uid: 'u1' };
    renderAt('/login?next=//evil.example');
    expect(screen.getByText('DASHBOARD ROUTE')).toBeInTheDocument();
  });

  it('does not redirect while auth is still loading', () => {
    mockUser = { uid: 'u1' };
    mockLoading = true;
    renderAt('/login?next=/invites/tok');
    expect(screen.queryByText('INVITE ROUTE')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
  });

  it('the mode toggle keeps next', () => {
    renderAt('/login?next=/invites/tok');
    fireEvent.click(screen.getByRole('button', { name: /Don't have an account/ }));
    expect(screen.getByRole('button', { name: 'Create Account' })).toBeInTheDocument();
    expect(screen.getByTestId('search')).toHaveTextContent('?next=/invites/tok');
  });

  it('links to the trust pages', async () => {
    renderAt('/login');
    expect(screen.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy');
    expect(screen.getByRole('link', { name: 'Data handling' })).toHaveAttribute('href', '/data-handling');

    mockLogin.mockRejectedValueOnce(new Error('auth/invalid-credential'));
    fillAndSubmitSignIn();
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password');
  });
});
