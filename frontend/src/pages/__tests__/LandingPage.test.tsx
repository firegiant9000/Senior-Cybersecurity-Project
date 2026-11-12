import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';

import LandingPage from '../LandingPage';

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_a: unknown, cb: (u: null) => void) => {
    cb(null)
    return vi.fn()
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}))

vi.mock('firebase/app', () => ({ initializeApp: vi.fn(() => ({})) }))

describe('LandingPage', () => {
  const renderPage = () =>
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

  it('contains no "free" or "credit card" wording', () => {
    renderPage();

    expect(screen.queryByText(/free/i)).toBeNull();
    expect(screen.queryByText(/credit card/i)).toBeNull();
  });

  it('links the footer to the trust pages', () => {
    renderPage();

    expect(screen.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy');
    expect(screen.getByRole('link', { name: 'Data handling' })).toHaveAttribute(
      'href',
      '/data-handling'
    );
  });
});
