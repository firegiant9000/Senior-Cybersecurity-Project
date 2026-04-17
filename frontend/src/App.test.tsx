import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_auth: unknown, callback: (user: null) => void) => {
    callback(null);
    return vi.fn();
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}))

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({})),
}))

vi.mock('./Dashboard.tsx', () => ({
  default: () => <div data-testid="dashboard">Dashboard</div>,
}))

import App from './App'
import { AuthProvider } from './context/AuthContext'

describe('App', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    )
    expect(document.body).toBeTruthy()
  })

  it('shows login page when unauthenticated', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    )

    expect(await screen.findByRole('heading', { name: /cyber threat intelligence/i })).toBeInTheDocument()
    expect(screen.getByText(/sign in to your account/i)).toBeInTheDocument()
    expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument()
  })
})
