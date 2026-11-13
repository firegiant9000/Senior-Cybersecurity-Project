import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockLogout,
  mockFetchWithAuth,
  mockListAgents,
  mockEnrollAgent,
  mockRotateAgent,
  mockRevokeAgent,
  mockEndAgentGrace,
  authState,
} = vi.hoisted(() => ({
  mockLogout: vi.fn(),
  mockFetchWithAuth: vi.fn(),
  mockListAgents: vi.fn(),
  mockEnrollAgent: vi.fn(),
  mockRotateAgent: vi.fn(),
  mockRevokeAgent: vi.fn(),
  mockEndAgentGrace: vi.fn(),
  // useAuth() values are lower-cased by the real AuthContext.
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

vi.mock('../../../api/agents', () => ({
  listAgents: (...args: unknown[]) => mockListAgents(...args),
  enrollAgent: (...args: unknown[]) => mockEnrollAgent(...args),
  rotateAgent: (...args: unknown[]) => mockRotateAgent(...args),
  revokeAgent: (...args: unknown[]) => mockRevokeAgent(...args),
  endAgentGrace: (...args: unknown[]) => mockEndAgentGrace(...args),
}))

// Import components AFTER mocks
import SettingsLayout from '../SettingsLayout'
import { AgentsPage, TeamPage } from '../pages'

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/settings/agents']}>
      <Routes>
        <Route element={<SettingsLayout />}>
          <Route path="/settings/team" element={<TeamPage />} />
          <Route path="/settings/agents" element={<AgentsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('AgentsPage - Scanner Agents', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.orgId = 1
    authState.role = 'user'
    authState.orgRole = 'owner'
    mockFetchWithAuth.mockResolvedValue({ ok: true, json: async () => ({}) })
    mockListAgents.mockResolvedValue({ items: [], total: 0 })
    mockEnrollAgent.mockResolvedValue(undefined)
    mockRotateAgent.mockResolvedValue(undefined)
    mockRevokeAgent.mockResolvedValue(undefined)
    mockEndAgentGrace.mockResolvedValue(undefined)
  })

  it('a member sees the admin-only line and no agents request', async () => {
    authState.orgRole = 'member'
    authState.role = 'user'

    renderPage()

    expect(screen.getByText('Only organisation admins can manage the team.')).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(mockListAgents).not.toHaveBeenCalled()
    expect(mockFetchWithAuth).not.toHaveBeenCalled()
  })

  describe('Scanner Agents - Rotate', () => {
    const agentWithStatus = (status: string) => ({
      id: 31,
      org_id: 1,
      name: 'web-01',
      token_prefix: 'deadbeef',
      scopes: null,
      created_by_user_id: 1,
      created_at: '2024-01-15T00:00:00Z',
      last_used_at: null,
      revoked_at: null,
      expires_at: null,
      status,
    })

    it('hides Rotate for an agent in grace', async () => {
      mockListAgents.mockResolvedValue({ items: [agentWithStatus('grace')], total: 1 })

      renderPage()

      await waitFor(() => {
        expect(screen.getByTitle('Revoke agent')).toBeInTheDocument()
      })
      expect(screen.queryByTitle('Rotate token')).not.toBeInTheDocument()
    })

    it('shows Rotate for an active agent', async () => {
      mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })

      renderPage()

      await waitFor(() => {
        expect(screen.getByTitle('Rotate token')).toBeInTheDocument()
      })
      expect(screen.getByTitle('Revoke agent')).toBeInTheDocument()
    })

    it('shows End grace now only for an agent in grace', async () => {
      mockListAgents.mockResolvedValue({ items: [agentWithStatus('grace')], total: 1 })

      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'End grace now' })).toBeInTheDocument()
      })
    })

    it('does not show End grace now for an active agent', async () => {
      mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })

      renderPage()

      await waitFor(() => {
        expect(screen.getByTitle('Rotate token')).toBeInTheDocument()
      })
      expect(screen.queryByRole('button', { name: 'End grace now' })).not.toBeInTheDocument()
    })

    describe('End grace confirmation', () => {
      afterEach(() => {
        vi.restoreAllMocks()
      })

      it('after confirming, calls the API client for that agent only', async () => {
        const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('grace')], total: 1 })
        renderPage()
        const button = await screen.findByRole('button', { name: 'End grace now' })

        fireEvent.click(button)

        await waitFor(() => {
          expect(mockEndAgentGrace).toHaveBeenCalledWith(31)
        })
        expect(String(confirmSpy.mock.calls[0][0])).toMatch(
          /old token stops working now.*switched to the new token/i,
        )
        expect(mockRevokeAgent).not.toHaveBeenCalled()
      })

      it('cancelling does nothing', async () => {
        const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('grace')], total: 1 })
        renderPage()
        const button = await screen.findByRole('button', { name: 'End grace now' })

        fireEvent.click(button)

        expect(confirmSpy).toHaveBeenCalledTimes(1)
        expect(mockEndAgentGrace).not.toHaveBeenCalled()
        expect(mockListAgents).toHaveBeenCalledTimes(1)
      })
    })

    describe('Revoke confirmation', () => {
      afterEach(() => {
        vi.restoreAllMocks()
      })

      it('asks first, says it covers rotated tokens, and cancelling does nothing', async () => {
        const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        renderPage()
        const button = await screen.findByTitle('Revoke agent')

        fireEvent.click(button)

        expect(confirmSpy).toHaveBeenCalledTimes(1)
        expect(String(confirmSpy.mock.calls[0][0])).toMatch(/every token rotated from this agent/i)
        expect(mockRevokeAgent).not.toHaveBeenCalled()
        expect(mockListAgents).toHaveBeenCalledTimes(1)
      })

      it('revokes after the user confirms', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true)
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        renderPage()
        const button = await screen.findByTitle('Revoke agent')

        fireEvent.click(button)

        await waitFor(() => {
          expect(mockRevokeAgent).toHaveBeenCalledWith(31)
        })
      })
    })

    it('does not promise that tokens rotated before the update are covered', async () => {
      mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })

      renderPage()

      expect(
        await screen.findByText(/tokens rotated before this update may not be linked/i),
      ).toBeInTheDocument()
    })
  })

})
