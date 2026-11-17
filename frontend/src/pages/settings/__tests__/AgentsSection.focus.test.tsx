import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockListAgents, mockRotateAgent, mockRevokeAgent, mockEndAgentGrace } = vi.hoisted(() => ({
  mockListAgents: vi.fn(),
  mockRotateAgent: vi.fn(),
  mockRevokeAgent: vi.fn(),
  mockEndAgentGrace: vi.fn(),
}))

vi.mock('../../../api/agents', () => ({
  listAgents: (...args: unknown[]) => mockListAgents(...args),
  enrollAgent: vi.fn(),
  rotateAgent: (...args: unknown[]) => mockRotateAgent(...args),
  revokeAgent: (...args: unknown[]) => mockRevokeAgent(...args),
  endAgentGrace: (...args: unknown[]) => mockEndAgentGrace(...args),
}))

import AgentsSection from '../AgentsSection'

function agent(id: number, status: string) {
  return {
    id,
    org_id: 1,
    name: `agent-${id}`,
    token_prefix: `pre${id}`,
    scopes: null,
    created_by_user_id: 1,
    created_at: '2024-01-01T00:00:00Z',
    last_used_at: null,
    revoked_at: status === 'revoked' ? '2024-02-01T00:00:00Z' : null,
    expires_at: null,
    status,
  }
}

function list(items: ReturnType<typeof agent>[]) {
  return { total: items.length, items }
}

async function confirmVia(triggerName: string, confirmName: string) {
  const trigger = screen.getByRole('button', { name: triggerName })
  trigger.focus()
  fireEvent.click(trigger)
  // "Rotate" is both the row trigger and the dialog confirm label, so scope to the dialog's confirm button.
  const confirmBtn = await waitFor(() => {
    const el = document.querySelector<HTMLButtonElement>('.confirm-btn-confirm')
    if (!el) throw new Error('confirm dialog not open')
    return el
  })
  expect(confirmBtn.textContent).toBe(confirmName)
  await act(async () => {
    fireEvent.click(confirmBtn)
  })
  return trigger
}

describe('AgentsSection focus after rotate / end grace / revoke', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('rotate focuses Copy token, never "I\'ve saved it"', async () => {
    mockListAgents
      .mockResolvedValueOnce(list([agent(1, 'active')]))
      .mockResolvedValue(list([agent(1, 'grace')]))
    mockRotateAgent.mockResolvedValue({ agent: agent(1, 'active'), raw_token: 'ht_secret_token' })
    render(<AgentsSection />)
    await screen.findByRole('button', { name: 'Rotate' })

    await confirmVia('Rotate', 'Rotate')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Copy token' })),
    )
    expect(document.activeElement).not.toBe(screen.getByRole('button', { name: "I've saved it" }))
  })

  it("revoke focuses the next agent's revoke button", async () => {
    // agent 2 stays listed as revoked with no buttons and must be skipped.
    // The reload is deferred to prove focus waits for it (i.e. `await loadAgents()` matters).
    let resolveReload!: (v: ReturnType<typeof list>) => void
    const reload = new Promise<ReturnType<typeof list>>((r) => {
      resolveReload = r
    })
    mockListAgents
      .mockResolvedValueOnce(list([agent(1, 'active'), agent(2, 'revoked'), agent(3, 'active')]))
      .mockReturnValueOnce(reload)
    mockRevokeAgent.mockResolvedValue(undefined)
    render(<AgentsSection />)
    await screen.findByRole('button', { name: 'Revoke agent-1' })

    await confirmVia('Revoke agent-1', 'Revoke')

    expect(screen.getByText('Loading agents...')).toBeTruthy()
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { name: 'Scanner Agents' }))

    await act(async () => {
      resolveReload(list([agent(1, 'revoked'), agent(2, 'revoked'), agent(3, 'active')]))
    })

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Revoke agent-3' })),
    )
  })

  it('end grace with no other grace agent focuses the heading', async () => {
    mockListAgents
      .mockResolvedValueOnce(list([agent(1, 'grace'), agent(2, 'active')]))
      .mockResolvedValue(list([agent(1, 'active'), agent(2, 'active')]))
    mockEndAgentGrace.mockResolvedValue(undefined)
    render(<AgentsSection />)
    await screen.findByRole('button', { name: 'End grace now' })

    await confirmVia('End grace now', 'End grace period')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Scanner Agents' })),
    )
  })

  it('failed revoke returns focus to the trigger', async () => {
    mockListAgents.mockResolvedValue(list([agent(1, 'active'), agent(2, 'active')]))
    mockRevokeAgent.mockRejectedValue(new Error('nope'))
    render(<AgentsSection />)
    await screen.findByRole('button', { name: 'Revoke agent-1' })

    await confirmVia('Revoke agent-1', 'Revoke')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Revoke agent-1' })),
    )
  })
})
