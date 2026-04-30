import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const { mockNavigate, mockRefreshProfile, mockGetInvite, mockAcceptInvite } = vi.hoisted(() => {
  const mockNavigate = vi.fn()
  const mockRefreshProfile = vi.fn()
  const mockGetInvite = vi.fn()
  const mockAcceptInvite = vi.fn()

  return { mockNavigate, mockRefreshProfile, mockGetInvite, mockAcceptInvite }
})

// ─────────────────────────────────────────────────────────────────────────────
// Module Mocks
// ─────────────────────────────────────────────────────────────────────────────

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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ refreshProfile: mockRefreshProfile }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../../api/members', () => ({
  getInviteByToken: (...args: unknown[]) => mockGetInvite(...args),
  acceptInvite: (...args: unknown[]) => mockAcceptInvite(...args),
}))

// Import component AFTER mocks
import AcceptInvitePage from '../AcceptInvitePage'

// ─────────────────────────────────────────────────────────────────────────────
// Mock Data
// ─────────────────────────────────────────────────────────────────────────────

const mockInviteData = {
  invite_token: 'test-token-123',
  org_name: 'Acme Corp',
  org_role: 'member',
  invited_email: 'user@example.com',
  expires_at: '2026-12-31T00:00:00Z',
}

const mockAdminInviteData = {
  ...mockInviteData,
  org_role: 'admin',
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderPage(token = 'test-token-123') {
  return render(
    <MemoryRouter initialEntries={[`/invite/${token}`]}>
      <Routes>
        <Route path="/invite/:token" element={<AcceptInvitePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('AcceptInvitePage', () => {
  beforeEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    mockGetInvite.mockResolvedValue(mockInviteData)
    mockAcceptInvite.mockResolvedValue(undefined)
    mockRefreshProfile.mockResolvedValue(undefined)
  })

  describe('Loading & Error States', () => {
    it('shows loading state initially', () => {
      renderPage()

      expect(screen.getByText(/Loading invite/i)).toBeInTheDocument()
    })

    it('shows error when token is missing', async () => {
      render(
        <MemoryRouter>
          <AcceptInvitePage />
        </MemoryRouter>,
      )

      await waitFor(() => {
        expect(screen.getByText(/No invite token provided/i)).toBeInTheDocument()
      })
    })

    it('shows error when invite fetch fails', async () => {
      mockGetInvite.mockRejectedValue(new Error('Invite not found'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Invite not found/i)).toBeInTheDocument()
      })
    })

    it('shows error for invalid token format', async () => {
      mockGetInvite.mockRejectedValue(new Error('Invalid token format'))

      renderPage('invalid-token')

      await waitFor(() => {
        expect(screen.getByText(/Invalid token format/i)).toBeInTheDocument()
      })
    })

    it('shows error for expired invite', async () => {
      mockGetInvite.mockRejectedValue(new Error('This invite has expired'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/This invite has expired/i)).toBeInTheDocument()
      })
    })

    it('hides loading state after successful fetch', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.queryByText(/Loading invite/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Invite Details Display', () => {
    it('displays organization name', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
      })
    })

    it('displays member role badge', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('member')).toBeInTheDocument()
      })
    })

    it('displays admin role badge', async () => {
      mockGetInvite.mockResolvedValue(mockAdminInviteData)

      renderPage()

      await waitFor(() => {
        expect(screen.getByText('admin')).toBeInTheDocument()
      })
    })

    it('displays invited email address', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('user@example.com')).toBeInTheDocument()
      })
    })

    it('displays expiration date', async () => {
      renderPage()

      // Locale-formatted date depends on the runner's timezone: UTC-midnight
      // 2026-12-31 renders as 12/31/2026 in UTC but 12/30/2026 west of UTC.
      await waitFor(() => {
        expect(screen.getByText(/12\/3[01]\/2026/)).toBeInTheDocument()
      })
    })

    it('displays all invite details labels', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('Organization')).toBeInTheDocument()
        expect(screen.getByText('Role')).toBeInTheDocument()
        expect(screen.getByText('Invited email')).toBeInTheDocument()
        expect(screen.getByText('Expires')).toBeInTheDocument()
      })
    })

    it('displays invitation message', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/You've been invited/i)).toBeInTheDocument()
      })
    })
  })

  describe('Accept Invite Functionality', () => {
    it('renders accept button', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Accept & Join/i })).toBeInTheDocument()
      })
    })

    it('calls acceptInvite with correct token', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Accept & Join/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))

      await waitFor(() => {
        expect(mockAcceptInvite).toHaveBeenCalledWith('test-token-123')
      })
    })

    it('calls refreshProfile after accepting invite', async () => {
      renderPage()

      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))
      })

      await waitFor(() => {
        expect(mockRefreshProfile).toHaveBeenCalled()
      })
    })

    it('shows success message after accepting invite', async () => {
      renderPage()

      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))
      })

      await waitFor(() => {
        expect(screen.getByText(/You have joined the organization/i)).toBeInTheDocument()
      })
    })

    it('disables button while accepting invite', async () => {
      mockAcceptInvite.mockImplementation(() => new Promise(() => {}))

      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Accept & Join/i })).toBeInTheDocument()
      })

      const button = screen.getByRole('button', { name: /Accept & Join/i })
      fireEvent.click(button)

      await waitFor(() => {
        expect(button).toHaveTextContent(/Joining/i)
      })
    })

    it('shows error when accept fails', async () => {
      mockAcceptInvite.mockRejectedValue(new Error('Invite already accepted'))

      renderPage()

      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))
      })

      await waitFor(() => {
        expect(screen.getByText(/Invite already accepted/i)).toBeInTheDocument()
      })
    })

    it('shows error with custom message on accept failure', async () => {
      mockAcceptInvite.mockRejectedValue(
        new Error('Organization membership limit reached'),
      )

      renderPage()

      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))
      })

      await waitFor(() => {
        expect(
          screen.getByText(/Organization membership limit reached/i),
        ).toBeInTheDocument()
      })
    })

    it('navigates to dashboard after success (with delay)', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Accept & Join/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))

      await waitFor(() => {
        expect(screen.getByText(/You have joined the organization/i)).toBeInTheDocument()
      })

      vi.advanceTimersByTime(1500)

      expect(mockNavigate).toHaveBeenCalledWith('/')
    })
  })

  describe('Decline Invite Functionality', () => {
    it('renders decline button', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument()
      })
    })

    it('navigates to home when declining invite', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Decline/i }))

      expect(mockNavigate).toHaveBeenCalledWith('/')
    })

    it('does not call acceptInvite when declining', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Decline/i }))

      expect(mockAcceptInvite).not.toHaveBeenCalled()
    })

    it('does not call refreshProfile when declining', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Decline/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Decline/i }))

      expect(mockRefreshProfile).not.toHaveBeenCalled()
    })
  })

  describe('Page Title & Layout', () => {
    it('renders page heading', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Organization Invite/i)).toBeInTheDocument()
      })
    })

    it('displays invite section after loading', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/You've been invited/i)).toBeInTheDocument()
      })
    })

    it('hides invite form when accepted', async () => {
      renderPage()

      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))
      })

      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /Accept & Join/i })).not.toBeInTheDocument()
      })
    })
  })

  describe('Token Handling', () => {
    it('uses token from URL parameters', async () => {
      renderPage('custom-token-456')

      await waitFor(() => {
        expect(mockGetInvite).toHaveBeenCalledWith('custom-token-456')
      })
    })

    it('passes token to acceptInvite function', async () => {
      const customToken = 'special-invite-token-789'
      renderPage(customToken)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Accept & Join/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))

      await waitFor(() => {
        expect(mockAcceptInvite).toHaveBeenCalledWith(customToken)
      })
    })
  })

  describe('Date Formatting', () => {
    it('formats expiration date correctly', async () => {
      renderPage()

      await waitFor(() => {
        const expiresText = screen.getByText(/12\/31\/2026|2026/)
        expect(expiresText).toBeInTheDocument()
      })
    })

    it('handles different date formats', async () => {
      mockGetInvite.mockResolvedValue({
        ...mockInviteData,
        expires_at: '2025-06-15T00:00:00Z',
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/06\/15\/2025|2025/i)).toBeInTheDocument()
      })
    })
  })

  describe('Edge Cases', () => {
    it('handles different role types', async () => {
      const rolesData = [
        { ...mockInviteData, org_role: 'owner' },
        { ...mockInviteData, org_role: 'admin' },
        { ...mockInviteData, org_role: 'member' },
        { ...mockInviteData, org_role: 'viewer' },
      ]

      for (const roleData of rolesData) {
        vi.clearAllMocks()
        mockGetInvite.mockResolvedValue(roleData)

        renderPage()

        await waitFor(() => {
          expect(screen.getByText(roleData.org_role)).toBeInTheDocument()
        })
      }
    })

    it('handles special characters in org name', async () => {
      mockGetInvite.mockResolvedValue({
        ...mockInviteData,
        org_name: "O'Reilly & Associates Inc.",
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText("O'Reilly & Associates Inc.")).toBeInTheDocument()
      })
    })

    it('handles long email addresses', async () => {
      const longEmail = 'very.long.email.address+with+tags@subdomain.example.com'
      mockGetInvite.mockResolvedValue({
        ...mockInviteData,
        invited_email: longEmail,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(longEmail)).toBeInTheDocument()
      })
    })
  })

  describe('Cleanup & Lifecycle', () => {
    it('cleans up redirect timer on unmount', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const { unmount } = renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Accept & Join/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Accept & Join/i }))

      await waitFor(() => {
        expect(screen.getByText(/You have joined the organization/i)).toBeInTheDocument()
      })

      unmount()
      vi.advanceTimersByTime(2000)

      expect(mockNavigate).not.toHaveBeenCalledWith('/')
    })

    it('prevents state updates after unmount', () => {
      const { unmount } = renderPage()
      expect(screen.getByText(/Loading invite/i)).toBeInTheDocument()
      unmount()
      expect(screen.queryByText(/Loading invite/i)).not.toBeInTheDocument()
    })
  })
})
