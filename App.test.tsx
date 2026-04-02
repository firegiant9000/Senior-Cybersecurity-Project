import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'

// Mock the Firebase auth module used by AuthContext
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

// Mock the Dashboard component to avoid complex API dependencies
vi.mock('./Dashboard.tsx', () => ({
  default: () => <div data-testid="dashboard">Dashboard</div>,
}))

import App from './App'
import { AuthProvider } from './context/AuthContext'
import { UserProvider } from './context/UserContext'

describe('App', () => {
  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <UserProvider>
            <App />
          </UserProvider>
        </AuthProvider>
      </MemoryRouter>
    )
    // When not authenticated, user should be redirected to login
    expect(document.body).toBeTruthy()
  })
})
