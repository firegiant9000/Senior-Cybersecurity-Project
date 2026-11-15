import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockFetchWithAuth,
  mockListAgents,
  mockEnrollAgent,
  mockRotateAgent,
  mockRevokeAgent,
  mockEndAgentGrace,
  authState,
} = vi.hoisted(() => ({
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
import { AgentsPage } from '../pages'

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

async function confirmInDialog(label: string) {
  const dialog = await screen.findByRole('alertdialog')
  fireEvent.click(within(dialog).getByRole('button', { name: label }))
  // Let the dialog's pending state and the follow-up list reload settle inside act.
  await waitFor(() => {
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/settings/agents']}>
      <Routes>
        <Route element={<SettingsLayout />}>
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

    expect(screen.getByText('Only organisation admins can manage scanner agents.')).toBeInTheDocument()
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

    describe('Rotate confirmation', () => {
      it('asks first; cancelling does not rotate', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        renderPage()

        fireEvent.click(await screen.findByTitle('Rotate token'))

        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByText('Rotate agent token')).toBeInTheDocument()
        expect(
          within(dialog).getByText(
            'Issue a new token for web-01? The current token keeps working for up to 24 hours.',
          ),
        ).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))

        await waitFor(() => {
          expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
        })
        expect(mockRotateAgent).not.toHaveBeenCalled()
        expect(mockListAgents).toHaveBeenCalledTimes(1)
      })

      it('after confirming, rotates once and still shows the new token', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        mockRotateAgent.mockResolvedValue({ raw_token: 'ht_fake_new_token_for_test', agent: agentWithStatus('grace') })
        renderPage()

        fireEvent.click(await screen.findByTitle('Rotate token'))
        await confirmInDialog('Rotate')

        await waitFor(() => {
          expect(mockRotateAgent).toHaveBeenCalledTimes(1)
        })
        expect(mockRotateAgent).toHaveBeenCalledWith(31)
        expect(await screen.findByText('ht_fake_new_token_for_test')).toBeInTheDocument()
      })

      it('shows the existing error when rotation fails', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        mockRotateAgent.mockRejectedValue(new Error('Rotate exploded'))
        renderPage()

        fireEvent.click(await screen.findByTitle('Rotate token'))
        await confirmInDialog('Rotate')

        expect(await screen.findByText('Rotate exploded')).toBeInTheDocument()
      })
    })

    describe('End grace confirmation', () => {
      it('cancelling does nothing', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('grace')], total: 1 })
        renderPage()

        fireEvent.click(await screen.findByRole('button', { name: 'End grace now' }))

        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByRole('heading', { name: 'End grace period' })).toBeInTheDocument()
        expect(
          within(dialog).getByText(
            'Stop accepting the old token for web-01 now? Agents still using it will fail to report.',
          ),
        ).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))

        await waitFor(() => {
          expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
        })
        expect(mockEndAgentGrace).not.toHaveBeenCalled()
        expect(mockListAgents).toHaveBeenCalledTimes(1)
      })

      it('after confirming, calls the API client for that agent only', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('grace')], total: 1 })
        renderPage()

        fireEvent.click(await screen.findByRole('button', { name: 'End grace now' }))
        await confirmInDialog('End grace period')

        await waitFor(() => {
          expect(mockEndAgentGrace).toHaveBeenCalledTimes(1)
        })
        expect(mockEndAgentGrace).toHaveBeenCalledWith(31)
        expect(mockRevokeAgent).not.toHaveBeenCalled()
      })

      it('shows the existing error when ending grace fails', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('grace')], total: 1 })
        mockEndAgentGrace.mockRejectedValue(new Error('Grace exploded'))
        renderPage()

        fireEvent.click(await screen.findByRole('button', { name: 'End grace now' }))
        await confirmInDialog('End grace period')

        expect(await screen.findByText('Grace exploded')).toBeInTheDocument()
      })
    })

    describe('Revoke confirmation', () => {
      it('cancelling does nothing', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        renderPage()

        fireEvent.click(await screen.findByRole('button', { name: 'Revoke web-01' }))

        const dialog = await screen.findByRole('alertdialog')
        expect(within(dialog).getByText('Revoke agent')).toBeInTheDocument()
        expect(
          within(dialog).getByText(
            'Revoke web-01? This also revokes every token rotated from it, including any new token. The host must be re-enrolled. To cut off only the old token, use End grace now instead.',
          ),
        ).toBeInTheDocument()
        fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))

        await waitFor(() => {
          expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
        })
        expect(mockRevokeAgent).not.toHaveBeenCalled()
        expect(mockListAgents).toHaveBeenCalledTimes(1)
      })

      it('revokes once after the user confirms', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        renderPage()

        fireEvent.click(await screen.findByTitle('Revoke agent'))
        await confirmInDialog('Revoke')

        await waitFor(() => {
          expect(mockRevokeAgent).toHaveBeenCalledTimes(1)
        })
        expect(mockRevokeAgent).toHaveBeenCalledWith(31)
      })

      it('shows the existing error when revoking fails', async () => {
        mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })
        mockRevokeAgent.mockRejectedValue(new Error('Revoke exploded'))
        renderPage()

        fireEvent.click(await screen.findByTitle('Revoke agent'))
        await confirmInDialog('Revoke')

        expect(await screen.findByText('Revoke exploded')).toBeInTheDocument()
      })
    })

    it('does not promise that tokens rotated before the update are covered', async () => {
      mockListAgents.mockResolvedValue({ items: [agentWithStatus('active')], total: 1 })

      renderPage()

      expect(
        await screen.findByText(/tokens rotated before this update may not be linked/i),
      ).toBeInTheDocument()
      expect(await screen.findByText(/every token rotated from it/i)).toBeInTheDocument()
    })
  })

})
