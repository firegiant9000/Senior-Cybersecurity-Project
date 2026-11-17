import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockListMembers, mockListInvites, mockRevokeInvite, mockRemoveMember } = vi.hoisted(() => ({
  mockListMembers: vi.fn(),
  mockListInvites: vi.fn(),
  mockRevokeInvite: vi.fn(),
  mockRemoveMember: vi.fn(),
}))

vi.mock('../../../api/members', () => ({
  listMembers: (...args: unknown[]) => mockListMembers(...args),
  listInvites: (...args: unknown[]) => mockListInvites(...args),
  createInvite: vi.fn(),
  revokeInvite: (...args: unknown[]) => mockRevokeInvite(...args),
  updateMemberRole: vi.fn(),
  removeMember: (...args: unknown[]) => mockRemoveMember(...args),
}))

import TeamSection from '../TeamSection'

const CURRENT_USER = 1

function member(id: number, role: string) {
  return {
    user_id: id,
    email: `user${id}@example.com`,
    role,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
  }
}

function invite(id: number) {
  return {
    id,
    org_id: 1,
    email: `invite${id}@example.com`,
    role: 'member',
    status: 'pending',
    inviter_id: CURRENT_USER,
    expires_at: '2030-01-01T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
  }
}

function page<T>(items: T[]) {
  return { total: items.length, page: 1, page_size: 20, items }
}

function renderSection() {
  return render(<TeamSection orgId={1} userId={CURRENT_USER} role="admin" orgRole="owner" />)
}

async function confirmVia(triggerName: string, confirmName: string, { focusTrigger = true } = {}) {
  const trigger = screen.getByRole('button', { name: triggerName })
  // Safari does not focus a button on mouse click; focusTrigger=false models that.
  if (focusTrigger) trigger.focus()
  fireEvent.click(trigger)
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: confirmName }))
  })
  return trigger
}

describe('TeamSection focus after remove/revoke', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListInvites.mockResolvedValue(page([]))
  })

  it("focuses the next member's remove button after removal", async () => {
    mockListMembers
      .mockResolvedValueOnce(page([member(11, 'member'), member(12, 'member'), member(13, 'member')]))
      .mockResolvedValue(page([member(12, 'member'), member(13, 'member')]))
    mockRemoveMember.mockResolvedValue(undefined)
    renderSection()
    await screen.findByRole('button', { name: 'Remove user11@example.com' })

    await confirmVia('Remove user11@example.com', 'Remove')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove user12@example.com' })),
    )
  })

  it("focuses the previous member's remove button when the last row is removed", async () => {
    // The owner row (no remove button) sits directly before the last row, so
    // the nearest previous neighbour must be skipped.
    mockListMembers
      .mockResolvedValueOnce(page([member(11, 'member'), member(10, 'owner'), member(12, 'member')]))
      .mockResolvedValue(page([member(11, 'member'), member(10, 'owner')]))
    mockRemoveMember.mockResolvedValue(undefined)
    renderSection()
    await screen.findByRole('button', { name: 'Remove user12@example.com' })

    await confirmVia('Remove user12@example.com', 'Remove')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove user11@example.com' })),
    )
  })

  it('focuses the Members heading when no other removable member remains', async () => {
    mockListMembers
      .mockResolvedValueOnce(page([member(10, 'owner'), member(11, 'member')]))
      .mockResolvedValue(page([member(10, 'owner')]))
    mockRemoveMember.mockResolvedValue(undefined)
    renderSection()
    await screen.findByRole('button', { name: 'Remove user11@example.com' })

    await confirmVia('Remove user11@example.com', 'Remove')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Members' })),
    )
  })

  it('returns focus to the remove button when removal fails', async () => {
    mockListMembers.mockResolvedValue(page([member(11, 'member'), member(12, 'member')]))
    mockRemoveMember.mockRejectedValue(new Error('nope'))
    renderSection()
    await screen.findByRole('button', { name: 'Remove user11@example.com' })

    await confirmVia('Remove user11@example.com', 'Remove')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove user11@example.com' })),
    )
  })

  it('waits for the reloaded list before moving focus', async () => {
    let resolveReload!: (v: unknown) => void
    mockListMembers
      .mockResolvedValueOnce(page([member(11, 'member'), member(12, 'member')]))
      .mockReturnValueOnce(new Promise((res) => { resolveReload = res }))
    mockRemoveMember.mockResolvedValue(undefined)
    renderSection()
    await screen.findByRole('button', { name: 'Remove user11@example.com' })

    await confirmVia('Remove user11@example.com', 'Remove')

    expect(screen.getByText('Loading members...')).toBeInTheDocument()
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { name: 'Members' }))

    await act(async () => {
      resolveReload(page([member(12, 'member')]))
    })

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove user12@example.com' })),
    )
  })

  it("returns to the failed row's own button even if the trigger was never focused", async () => {
    mockListMembers.mockResolvedValue(page([member(11, 'member'), member(12, 'member')]))
    mockRemoveMember.mockRejectedValue(new Error('nope'))
    renderSection()
    await screen.findByRole('button', { name: 'Remove user11@example.com' })

    await confirmVia('Remove user11@example.com', 'Remove', { focusTrigger: false })

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove user11@example.com' })),
    )
  })

  it("focuses the next invite's revoke button after revoking", async () => {
    mockListMembers.mockResolvedValue(page([member(10, 'owner')]))
    mockListInvites
      .mockResolvedValueOnce(page([invite(21), invite(22)]))
      .mockResolvedValue(page([invite(22)]))
    mockRevokeInvite.mockResolvedValue(undefined)
    renderSection()
    await screen.findByRole('button', { name: 'Revoke invite for invite21@example.com' })

    await confirmVia('Revoke invite for invite21@example.com', 'Revoke')

    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: 'Revoke invite for invite22@example.com' }),
      ),
    )
  })
})
