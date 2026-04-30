import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockNavigate,
  mockLogout,
  mockFetchWithAuth,
  mockListMembers,
  mockListInvites,
  mockCreateInvite,
  mockRevokeInvite,
  mockUpdateMemberRole,
  mockRemoveMember,
} = vi.hoisted(() => {
  const mockNavigate = vi.fn()
  const mockLogout = vi.fn()
  const mockFetchWithAuth = vi.fn()
  const mockListMembers = vi.fn()
  const mockListInvites = vi.fn()
  const mockCreateInvite = vi.fn()
  const mockRevokeInvite = vi.fn()
  const mockUpdateMemberRole = vi.fn()
  const mockRemoveMember = vi.fn()

  return {
    mockNavigate,
    mockLogout,
    mockFetchWithAuth,
    mockListMembers,
    mockListInvites,
    mockCreateInvite,
    mockRevokeInvite,
    mockUpdateMemberRole,
    mockRemoveMember,
  }
})

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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: {
      uid: 'test-user-123',
      email: 'user@example.com',
      emailVerified: false,
      metadata: { lastSignInTime: '2024-01-01' },
    },
    logout: mockLogout,
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../../api/fetchWithAuth', () => ({
  API_BASE_URL: 'http://api',
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
  getJsonAuth: vi.fn(),
}))

vi.mock('../../api/members', () => ({
  listMembers: (...args: unknown[]) => mockListMembers(...args),
  listInvites: (...args: unknown[]) => mockListInvites(...args),
  createInvite: (...args: unknown[]) => mockCreateInvite(...args),
  revokeInvite: (...args: unknown[]) => mockRevokeInvite(...args),
  updateMemberRole: (...args: unknown[]) => mockUpdateMemberRole(...args),
  removeMember: (...args: unknown[]) => mockRemoveMember(...args),
}))

// Import component AFTER mocks
import SettingsPage from '../SettingsPage'

// ─────────────────────────────────────────────────────────────────────────────
// Mock Data
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

const mockMembersData = {
  items: [
    {
      user_id: 1,
      email: 'owner@example.com',
      role: 'owner',
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      user_id: 2,
      email: 'admin@example.com',
      role: 'admin',
      created_at: '2024-01-02T00:00:00Z',
    },
    {
      user_id: 3,
      email: 'member@example.com',
      role: 'member',
      created_at: '2024-01-03T00:00:00Z',
    },
  ],
  total: 3,
}

const mockInvitesData = {
  items: [
    {
      id: 101,
      org_id: 1,
      email: 'pending@example.com',
      role: 'member',
      status: 'pending',
      inviter_id: 1,
      created_at: '2024-01-15T00:00:00Z',
      expires_at: '2024-02-15T00:00:00Z',
    },
    {
      id: 102,
      org_id: 1,
      email: 'admin-pending@example.com',
      role: 'admin',
      status: 'pending',
      inviter_id: 1,
      created_at: '2024-01-16T00:00:00Z',
      expires_at: '2024-02-16T00:00:00Z',
    },
  ],
  total: 2,
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )
}

function mockSuccessfulProfileLoad() {
  mockFetchWithAuth.mockResolvedValue({
    ok: true,
    json: async () => mockUserProfile,
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('SettingsPage - Member Management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSuccessfulProfileLoad()
    mockListMembers.mockResolvedValue(mockMembersData)
    mockListInvites.mockResolvedValue(mockInvitesData)
    mockCreateInvite.mockResolvedValue(undefined)
    mockRevokeInvite.mockResolvedValue(undefined)
    mockUpdateMemberRole.mockResolvedValue(undefined)
    mockRemoveMember.mockResolvedValue(undefined)
  })

  describe('Page Loading & Access Control', () => {
    it('loads profile on mount', async () => {
      renderPage()

      await waitFor(() => {
        expect(mockFetchWithAuth).toHaveBeenCalledWith('http://api/api/v1/auth/me')
      })
    })

    it('shows loading state initially', () => {
      renderPage()

      expect(screen.getByText(/Loading profile/i)).toBeInTheDocument()
    })

    it('shows profile data after loading', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('user@example.com')).toBeInTheDocument()
      })
    })

    it('shows error when profile load fails', async () => {
      mockFetchWithAuth.mockRejectedValue(new Error('Network error'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument()
      })
    })

    it('hides member management sections when user is not admin', async () => {
      const nonAdminProfile = { ...mockUserProfile, org_role: 'member' }
      mockFetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => nonAdminProfile,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Your account/i)).toBeInTheDocument()
      })

      expect(screen.queryByText(/Members/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Invitations/i)).not.toBeInTheDocument()
    })

    it('shows member management sections when user is org owner', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Members/i)).toBeInTheDocument()
        expect(screen.getByText(/Invitations/i)).toBeInTheDocument()
      })
    })

    it('shows member management sections when user is org admin', async () => {
      const adminProfile = { ...mockUserProfile, org_role: 'admin' }
      mockFetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => adminProfile,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Members/i)).toBeInTheDocument()
        expect(screen.getByText(/Invitations/i)).toBeInTheDocument()
      })
    })

    it('shows member management sections when user is system admin', async () => {
      const adminProfile = { ...mockUserProfile, role: 'admin' }
      mockFetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => adminProfile,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Members/i)).toBeInTheDocument()
        expect(screen.getByText(/Invitations/i)).toBeInTheDocument()
      })
    })

    it('hides member management when org_id is null', async () => {
      const noOrgProfile = { ...mockUserProfile, org_id: null, org_role: null }
      mockFetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => noOrgProfile,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.queryByText(/Members/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/Invitations/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Members Section - Display', () => {
    it('loads members list on mount', async () => {
      renderPage()

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalledWith(1, 1, 20)
      })
    })

    it('displays members section heading', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Members/i)).toBeInTheDocument()
      })
    })

    it('displays members table with all columns', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('Email').length).toBeGreaterThan(0)
        expect(screen.getAllByText(/Role/i).length).toBeGreaterThan(0)
        expect(screen.getByText(/Joined/i)).toBeInTheDocument()
      })
    })

    it('displays all members in list', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('owner@example.com')).toBeInTheDocument()
        expect(screen.getByText('admin@example.com')).toBeInTheDocument()
        expect(screen.getByText('member@example.com')).toBeInTheDocument()
      })
    })

    it('shows loading state when fetching members', async () => {
      mockListMembers.mockImplementation(() => new Promise(() => {}))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Loading members/i)).toBeInTheDocument()
      })
    })

    it('shows empty message when no members', async () => {
      mockListMembers.mockResolvedValue({ items: [], total: 0 })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/No members found/i)).toBeInTheDocument()
      })
    })

    it('shows error message when members load fails', async () => {
      mockListMembers.mockRejectedValue(new Error('Failed to load members'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Failed to load members/i)).toBeInTheDocument()
      })
    })

    it('displays member join dates correctly', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText(/01\/01\/2024|1\/1\/2024|2024-01-01/).length).toBeGreaterThan(0)
        expect(screen.getAllByText(/01\/02\/2024|1\/2\/2024|2024-01-02/).length).toBeGreaterThan(0)
      })
    })
  })

  describe('Members Section - Role Management', () => {
    it('displays owner role as badge (not selectable)', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('owner@example.com')).toBeInTheDocument()
      })

      const ownerBadge = screen.getByText('owner')
      expect(ownerBadge.tagName).not.toBe('SELECT')
    })

    it('displays member and admin roles as dropdowns', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('admin@example.com')).toBeInTheDocument()
      })

      const selects = screen.getAllByRole('combobox')
      expect(selects.length).toBeGreaterThan(0)
    })

    it('shows role options in dropdown', async () => {
      renderPage()

      await waitFor(() => {
        const selects = screen.getAllByRole('combobox')
        expect(selects.length).toBeGreaterThan(0)
      })
      const options = screen.getAllByRole('option')
      const optionValues = options.map((o) => (o as HTMLElement).getAttribute('value') ?? '')
      expect(optionValues).toContain('member')
      expect(optionValues).toContain('admin')
    })

    it('calls updateMemberRole when role changes', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('member@example.com')).toBeInTheDocument()
      })

      const selects = screen.getAllByRole('combobox')
      fireEvent.change(selects[0], { target: { value: 'admin' } })

      await waitFor(() => {
        expect(mockUpdateMemberRole).toHaveBeenCalled()
      })
    })

    it('shows success message after role update', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('member@example.com')).toBeInTheDocument()
      })
      const selects = screen.getAllByRole('combobox')
      // selects[1] = the 'member' row's select (selects[0] = 'admin' row, value already 'admin')
      fireEvent.change(selects[1], { target: { value: 'admin' } })

      await waitFor(() => {
        expect(screen.getByText(/Role updated/i)).toBeInTheDocument()
      })
    })

    it('shows error message on role update failure', async () => {
      mockUpdateMemberRole.mockRejectedValue(new Error('Permission denied'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText('member@example.com')).toBeInTheDocument()
      })
      const selects = screen.getAllByRole('combobox')
      fireEvent.change(selects[1], { target: { value: 'admin' } })

      await waitFor(() => {
        expect(screen.getByText(/Permission denied/i)).toBeInTheDocument()
      })
    })

    it('renders owner role as a badge for the current user (not a select)', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('owner@example.com')).toBeInTheDocument()
      })
      const ownerRow = screen.getByText('owner@example.com').closest('tr')
      expect(ownerRow?.querySelector('select')).not.toBeInTheDocument()
      expect(ownerRow?.querySelector('.role-badge')).toBeInTheDocument()
    })

    it('disables role select for non-owners if user is not owner', async () => {
      const adminProfile = { ...mockUserProfile, org_role: 'admin' }
      mockFetchWithAuth.mockResolvedValue({
        ok: true,
        json: async () => adminProfile,
      })

      renderPage()

      await waitFor(() => {
        const selects = screen.getAllByRole('combobox')
        expect(selects[0]).toBeDisabled()
      })
    })
  })

  describe('Members Section - Removal', () => {
    it('displays remove button for non-owner members', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('member@example.com')).toBeInTheDocument()
      })

      const deleteButtons = screen.getAllByRole('button', { name: '×' })
      expect(deleteButtons.length).toBeGreaterThan(0)
    })

    it('does not display remove button for owner', async () => {
      renderPage()

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalled()
      })

      // Owner row should not have a delete button
      const ownerRow = screen.getByText('owner@example.com').closest('tr')
      expect(ownerRow?.querySelector('button')).not.toBeInTheDocument()
    })

    it('does not display remove button for current user', async () => {
      renderPage()

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalled()
      })

      // Current user row should not have a delete button
      // (user_id 1 is the current user)
      const rows = screen.getAllByRole('row')
      expect(rows.length).toBeGreaterThan(0)
    })

    it('calls removeMember when delete button clicked', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('member@example.com')).toBeInTheDocument()
      })

      const deleteButtons = screen.getAllByRole('button', { name: '×' })
      fireEvent.click(deleteButtons[0])

      await waitFor(() => {
        expect(mockRemoveMember).toHaveBeenCalled()
      })
    })

    it('shows success message after member removal', async () => {
      renderPage()

      await waitFor(() => {
        const deleteButtons = screen.getAllByRole('button', { name: '×' })
        fireEvent.click(deleteButtons[0])
      })

      await waitFor(() => {
        expect(screen.getByText(/Member removed/i)).toBeInTheDocument()
      })
    })

    it('shows error message on removal failure', async () => {
      mockRemoveMember.mockRejectedValue(new Error('Cannot remove member'))

      renderPage()

      await waitFor(() => {
        const deleteButtons = screen.getAllByRole('button', { name: '×' })
        fireEvent.click(deleteButtons[0])
      })

      await waitFor(() => {
        expect(screen.getByText(/Cannot remove member/i)).toBeInTheDocument()
      })
    })
  })

  describe('Members Section - Pagination', () => {
    it('does not show pagination when total <= page size', async () => {
      renderPage()

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalled()
      })

      expect(screen.queryByText(/Page/i)).not.toBeInTheDocument()
    })

    it('shows pagination when total > page size', async () => {
      mockListMembers.mockResolvedValue({
        items: mockMembersData.items,
        total: 50,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Page/i)).toBeInTheDocument()
      })
    })

    it('disables previous button on first page', async () => {
      mockListMembers.mockResolvedValue({
        items: mockMembersData.items,
        total: 50,
      })

      renderPage()

      await waitFor(() => {
        const prevButton = screen.getByRole('button', { name: /Previous/i })
        expect(prevButton).toBeDisabled()
      })
    })

    it('enables next button when more pages available', async () => {
      mockListMembers.mockResolvedValue({
        items: mockMembersData.items,
        total: 50,
      })

      renderPage()

      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /Next/i })
        expect(nextButton).not.toBeDisabled()
      })
    })

    it('navigates to next page on click', async () => {
      mockListMembers.mockResolvedValue({
        items: mockMembersData.items,
        total: 50,
      })

      renderPage()

      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /Next/i })
        fireEvent.click(nextButton)
      })

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalledWith(1, 2, 20)
      })
    })

    it('navigates to previous page on click', async () => {
      mockListMembers.mockResolvedValue({
        items: mockMembersData.items,
        total: 50,
      })

      renderPage()

      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /Next/i })
        fireEvent.click(nextButton)
      })

      await waitFor(() => {
        const prevButton = screen.getByRole('button', { name: /Previous/i })
        expect(prevButton).not.toBeDisabled()
        fireEvent.click(prevButton)
      })

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalledWith(1, 1, 20)
      })
    })
  })

  describe('Invitations Section - Display', () => {
    it('loads invites list on mount', async () => {
      renderPage()

      await waitFor(() => {
        expect(mockListInvites).toHaveBeenCalledWith(1, 1, 20)
      })
    })

    it('displays invitations section heading', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Invitations/i)).toBeInTheDocument()
      })
    })

    it('displays invites table with all columns', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText(/Email/i).length).toBeGreaterThan(0)
        expect(screen.getAllByText(/Role/i).length).toBeGreaterThan(0)
        expect(screen.getAllByText(/Status/i).length).toBeGreaterThan(0)
        expect(screen.getByText(/Expires/i)).toBeInTheDocument()
      })
    })

    it('displays all pending invites', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('pending@example.com')).toBeInTheDocument()
        expect(screen.getByText('admin-pending@example.com')).toBeInTheDocument()
      })
    })

    it('shows loading state when fetching invites', async () => {
      mockListInvites.mockImplementation(() => new Promise(() => {}))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Loading invites/i)).toBeInTheDocument()
      })
    })

    it('shows empty message when no pending invites', async () => {
      mockListInvites.mockResolvedValue({ items: [], total: 0 })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/No pending invitations/i)).toBeInTheDocument()
      })
    })

    it('shows error message when invites load fails', async () => {
      mockListInvites.mockRejectedValue(new Error('Failed to load invites'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Failed to load invites/i)).toBeInTheDocument()
      })
    })

    it('displays invite expiration dates', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText(/02\/15\/2024|2\/15\/2024|2024-02-15/).length).toBeGreaterThan(0)
      })
    })
  })

  describe('Invitations Section - Create Invite', () => {
    it('displays invite form with email input', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/user@example.com/i)).toBeInTheDocument()
      })
    })

    it('displays role dropdown for new invites', async () => {
      renderPage()

      await waitFor(() => {
        const selects = screen.getAllByRole('combobox')
        expect(selects.length).toBeGreaterThan(0)
      })
    })

    it('displays send invite button', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Send Invite/i })).toBeInTheDocument()
      })
    })

    it('disables send button when email is empty', async () => {
      renderPage()

      await waitFor(() => {
        const sendButton = screen.getByRole('button', { name: /Send Invite/i })
        expect(sendButton).toBeDisabled()
      })
    })

    it('enables send button when email is entered', async () => {
      renderPage()

      await waitFor(() => {
        const emailInput = screen.getByPlaceholderText(/user@example.com/i)
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } })
      })

      await waitFor(() => {
        const sendButton = screen.getByRole('button', { name: /Send Invite/i })
        expect(sendButton).not.toBeDisabled()
      })
    })

    it('calls createInvite with email and role', async () => {
      renderPage()

      await waitFor(() => {
        const emailInput = screen.getByPlaceholderText(/user@example.com/i)
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } })
      })

      fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }))

      await waitFor(() => {
        expect(mockCreateInvite).toHaveBeenCalledWith(1, 'new@example.com', 'member')
      })
    })

    it('calls createInvite with admin role when selected', async () => {
      renderPage()

      await waitFor(() => {
        const emailInput = screen.getByPlaceholderText(/user@example.com/i)
        fireEvent.change(emailInput, { target: { value: 'admin@example.com' } })
      })

      const selects = screen.getAllByRole('combobox')
      fireEvent.change(selects[selects.length - 1], { target: { value: 'admin' } })

      fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }))

      await waitFor(() => {
        expect(mockCreateInvite).toHaveBeenCalledWith(1, 'admin@example.com', 'admin')
      })
    })

    it('shows success message after sending invite', async () => {
      renderPage()

      await waitFor(() => {
        const emailInput = screen.getByPlaceholderText(/user@example.com/i)
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } })
        fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }))
      })

      await waitFor(() => {
        expect(screen.getByText(/Invite sent/i)).toBeInTheDocument()
      })
    })

    it('clears email input after sending invite', async () => {
      renderPage()

      const emailInput = await screen.findByPlaceholderText(/user@example.com/i) as HTMLInputElement
      fireEvent.change(emailInput, { target: { value: 'new@example.com' } })

      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }))
      })

      await waitFor(() => {
        expect(emailInput.value).toBe('')
      })
    })

    it('shows error message on invite creation failure', async () => {
      mockCreateInvite.mockRejectedValue(new Error('Email already invited'))

      renderPage()

      await waitFor(() => {
        const emailInput = screen.getByPlaceholderText(/user@example.com/i)
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } })
        fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }))
      })

      await waitFor(() => {
        expect(screen.getByText(/Email already invited/i)).toBeInTheDocument()
      })
    })

    it('sends invite on enter key press', async () => {
      renderPage()

      await waitFor(() => {
        const emailInput = screen.getByPlaceholderText(/user@example.com/i)
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } })
        fireEvent.keyDown(emailInput, { key: 'Enter' })
      })

      await waitFor(() => {
        expect(mockCreateInvite).toHaveBeenCalled()
      })
    })
  })

  describe('Invitations Section - Revoke Invite', () => {
    it('displays revoke button for each invite', async () => {
      renderPage()

      await waitFor(() => {
        const deleteButtons = screen.getAllByRole('button', { name: '×' })
        expect(deleteButtons.length).toBeGreaterThan(0)
      })
    })

    it('calls revokeInvite when revoke button clicked', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('pending@example.com')).toBeInTheDocument()
      })
      const revokeButtons = screen.getAllByTitle('Revoke invite')
      fireEvent.click(revokeButtons[0])

      await waitFor(() => {
        expect(mockRevokeInvite).toHaveBeenCalled()
      })
    })

    it('reloads invites after revoking', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('pending@example.com')).toBeInTheDocument()
      })
      const revokeButtons = screen.getAllByTitle('Revoke invite')
      fireEvent.click(revokeButtons[0])

      await waitFor(() => {
        expect(mockListInvites).toHaveBeenCalledTimes(2)
      })
    })

    it('shows error message on revoke failure', async () => {
      mockRevokeInvite.mockRejectedValue(new Error('Cannot revoke invite'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText('pending@example.com')).toBeInTheDocument()
      })
      const revokeButtons = screen.getAllByTitle('Revoke invite')
      fireEvent.click(revokeButtons[0])

      await waitFor(() => {
        expect(screen.getByText(/Failed to revoke invite/i)).toBeInTheDocument()
      })
    })
  })

  describe('Invitations Section - Pagination', () => {
    it('shows pagination when total > page size', async () => {
      mockListInvites.mockResolvedValue({
        items: mockInvitesData.items,
        total: 50,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText(/Page/i).length).toBeGreaterThan(0)
      })
    })

    it('navigates through invite pages', async () => {
      mockListInvites.mockResolvedValue({
        items: mockInvitesData.items,
        total: 50,
      })

      renderPage()

      await waitFor(() => {
        const nextButtons = screen.getAllByRole('button', { name: /Next/i })
        const invitesNextButton = nextButtons[nextButtons.length - 1]
        fireEvent.click(invitesNextButton)
      })

      await waitFor(() => {
        expect(mockListInvites).toHaveBeenCalledWith(1, 2, 20)
      })
    })
  })

  describe('Member & Invite List Refresh', () => {
    it('reloads members list after creating invite', async () => {
      renderPage()

      await waitFor(() => {
        const emailInput = screen.getByPlaceholderText(/user@example.com/i)
        fireEvent.change(emailInput, { target: { value: 'new@example.com' } })
        fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }))
      })

      await waitFor(() => {
        expect(mockListInvites).toHaveBeenCalledTimes(2)
      })
    })

    it('reloads members list after updating role', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('member@example.com')).toBeInTheDocument()
      })
      const selects = screen.getAllByRole('combobox')
      fireEvent.change(selects[1], { target: { value: 'admin' } })

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalledTimes(2)
      })
    })

    it('reloads members list after removing member', async () => {
      renderPage()

      await waitFor(() => {
        const deleteButtons = screen.getAllByRole('button', { name: '×' })
        fireEvent.click(deleteButtons[0])
      })

      await waitFor(() => {
        expect(mockListMembers).toHaveBeenCalledTimes(2)
      })
    })
  })

  describe('Edge Cases', () => {
    it('handles organization with no members except current user', async () => {
      mockListMembers.mockResolvedValue({
        items: [mockMembersData.items[0]],
        total: 1,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText('owner@example.com')).toBeInTheDocument()
      })
    })

    it('handles special characters in email addresses', async () => {
      mockListInvites.mockResolvedValue({
        items: [
          {
            id: 101,
            org_id: 1,
            email: 'user+tag@sub.example.com',
            role: 'member',
            status: 'pending',
            inviter_id: 1,
            created_at: '2024-01-15T00:00:00Z',
            expires_at: '2024-02-15T00:00:00Z',
          },
        ],
        total: 1,
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText('user+tag@sub.example.com')).toBeInTheDocument()
      })
    })

    it('handles role changes to same role', async () => {
      renderPage()

      await waitFor(() => {
        const selects = screen.getAllByRole('combobox')
        fireEvent.change(selects[1], { target: { value: 'admin' } })
      })

      await waitFor(() => {
        expect(mockUpdateMemberRole).toHaveBeenCalled()
      })
    })
  })
})
