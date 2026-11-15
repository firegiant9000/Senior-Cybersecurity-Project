import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import IntegrationsPage from '../IntegrationsPage'

const { mockFetchM365Status } = vi.hoisted(() => ({
  mockFetchM365Status: vi.fn(),
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ orgId: 7 }),
}))

vi.mock('../../api/integrations', () => ({
  fetchM365Status: mockFetchM365Status,
  startM365Consent: vi.fn(),
  syncM365: vi.fn(),
  disconnectM365: vi.fn(),
}))

describe('IntegrationsPage when Microsoft 365 sync is disabled', () => {
  it('explains the sync is unavailable and links to the inventory upload', async () => {
    mockFetchM365Status.mockResolvedValue({ enabled: false })

    const { container } = render(
      <MemoryRouter>
        <IntegrationsPage />
      </MemoryRouter>,
    )

    expect(
      await screen.findByText(/Microsoft 365 sync isn't available on this deployment yet/),
    ).toBeInTheDocument()

    const link = screen.getByRole('link', { name: 'uploading an inventory file' })
    expect(link).toHaveAttribute('href', '/inventory/upload')

    expect(container.textContent).not.toMatch(/ENABLE_M365_INTEGRATION/)
    expect(container.querySelector('code')).toBeNull()
  })
})
