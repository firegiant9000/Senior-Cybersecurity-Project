import { render, screen, waitFor, within, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IntegrationsPage from '../IntegrationsPage'

const { mockFetchStatus, mockDisconnect, mockSync, mockConsent } = vi.hoisted(() => ({
  mockFetchStatus: vi.fn(),
  mockDisconnect: vi.fn(),
  mockSync: vi.fn(),
  mockConsent: vi.fn(),
}))

vi.mock('../../context/AuthContext.tsx', () => ({
  useAuth: () => ({ orgId: 7 }),
}))

vi.mock('../../api/integrations.ts', () => ({
  fetchM365Status: mockFetchStatus,
  disconnectM365: mockDisconnect,
  syncM365: mockSync,
  startM365Consent: mockConsent,
}))

const connected = { enabled: true, connection: { connected: true, status: 'active' } }

function renderPage() {
  return render(
    <MemoryRouter>
      <IntegrationsPage />
    </MemoryRouter>,
  )
}

async function clickDisconnect() {
  fireEvent.click(await screen.findByTestId('m365-disconnect'))
  return screen.findByRole('alertdialog')
}

describe('IntegrationsPage disconnect confirm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchStatus.mockResolvedValue(connected)
    mockDisconnect.mockResolvedValue(undefined)
  })

  it('shows the dialog and makes no call on Cancel', async () => {
    renderPage()
    const dialog = await clickDisconnect()
    expect(within(dialog).getByText('Disconnect Microsoft 365')).toBeInTheDocument()
    expect(
      within(dialog).getByText(
        'Disconnect Microsoft 365? Asset sync stops until you connect again.',
      ),
    ).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })
    expect(mockDisconnect).not.toHaveBeenCalled()
  })

  it('disconnects once on Confirm', async () => {
    renderPage()
    const dialog = await clickDisconnect()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Disconnect' }))
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })
    expect(mockDisconnect).toHaveBeenCalledTimes(1)
    expect(mockDisconnect).toHaveBeenCalledWith(7)
  })

  it('dialog stays gone after the status refetch that follows a disconnect', async () => {
    renderPage()
    const dialog = await clickDisconnect()
    let release!: () => void
    mockFetchStatus.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ enabled: true, connection: { connected: false } })
        }),
    )
    fireEvent.click(within(dialog).getByRole('button', { name: 'Disconnect' }))
    await waitFor(() => {
      expect(mockFetchStatus).toHaveBeenCalledTimes(2)
    })
    await act(async () => {
      release()
    })
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })
    expect(mockDisconnect).toHaveBeenCalledTimes(1)
  })

  it('closes the dialog and shows the error when the API rejects', async () => {
    mockDisconnect.mockRejectedValue(new Error('Disconnect blew up'))
    renderPage()
    const dialog = await clickDisconnect()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Disconnect' }))
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })
    expect(await screen.findByRole('alert')).toHaveTextContent('Disconnect blew up')
  })
})
