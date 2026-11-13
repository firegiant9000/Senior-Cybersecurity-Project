import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const { mockLogout, mockFetchWithAuth, authState } = vi.hoisted(() => ({
  mockLogout: vi.fn(),
  mockFetchWithAuth: vi.fn(),
  authState: {
    orgId: 1 as number | null,
    role: 'user' as string | null,
    orgRole: 'owner' as string | null,
  },
}))

// ─────────────────────────────────────────────────────────────────────────────
// Module Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: { emailVerified: false, metadata: { lastSignInTime: '2024-01-01' } } })),
  onAuthStateChanged: vi.fn((_a: unknown, cb: (u: unknown) => void) => {
    cb({
      uid: 'test-user-123',
      email: 'user@example.com',
      emailVerified: false,
      metadata: { lastSignInTime: '2024-01-01' },
    })
    return vi.fn()
  }),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock('firebase/app', () => ({ initializeApp: vi.fn(() => ({})) }))

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      uid: 'test-user-123',
      email: 'user@example.com',
      emailVerified: false,
      metadata: { lastSignInTime: '2024-01-01' },
    },
    orgId: authState.orgId,
    role: authState.role,
    orgRole: authState.orgRole,
    logout: mockLogout,
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../../../api/fetchWithAuth', () => ({
  API_BASE_URL: 'http://api',
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
  getJsonAuth: vi.fn(),
}))

// Import components AFTER mocks
import SettingsLayout from '../SettingsLayout'
import { AccountPage } from '../pages'

// ─────────────────────────────────────────────────────────────────────────────
// Helpers and fixtures
// ─────────────────────────────────────────────────────────────────────────────

const mockUserProfile = {
  id: 1,
  email: 'user@example.com',
  is_active: true,
  role: 'user',
  auth_provider: 'google',
  created_at: '2024-01-01T00:00:00Z',
  org_id: 1,
  org_role: 'owner',
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/settings/account']}>
      <Routes>
        <Route element={<SettingsLayout />}>
          <Route path="/settings/account" element={<AccountPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AccountPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.orgId = 1
    authState.role = 'user'
    authState.orgRole = 'owner'
    mockFetchWithAuth.mockResolvedValue({ ok: true, json: async () => mockUserProfile })
  })

  it('shows profile data after loading', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('user@example.com')).toBeInTheDocument()
    })
  })
})
