import { render, screen, waitFor, within, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IntegrationsPage from '../IntegrationsPage'
import UploadInventoryPage from '../UploadInventoryPage'

const {
  mockFetchStatus,
  mockDisconnect,
  mockPreview,
  mockImport,
  mockRollback,
  mockGetRun,
  mockGetDiff,
} = vi.hoisted(() => ({
  mockFetchStatus: vi.fn(),
  mockDisconnect: vi.fn(),
  mockPreview: vi.fn(),
  mockImport: vi.fn(),
  mockRollback: vi.fn(),
  mockGetRun: vi.fn(),
  mockGetDiff: vi.fn(),
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ orgId: 7 }),
}))

vi.mock('../../api/integrations.ts', () => ({
  fetchM365Status: mockFetchStatus,
  disconnectM365: mockDisconnect,
  syncM365: vi.fn(),
  startM365Consent: vi.fn(),
}))

vi.mock('../../api/analytics', () => ({
  logActivationEvent: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../api/inventory', () => ({
  previewInventoryCsv: mockPreview,
  importInventoryCsv: mockImport,
  rollbackScanRun: mockRollback,
  getScanRun: mockGetRun,
  getScanRunDiff: mockGetDiff,
}))

vi.mock('../../hooks/useDataStatus', () => ({
  useDataStatus: () => ({ byKey: {}, loading: false }),
}))

const connected = { enabled: true, connection: { connected: true, status: 'active' } }
const notConnected = { enabled: true, connection: { connected: false } }

const run = {
  id: 42,
  org_id: 7,
  source: 'csv_upload',
  status: 'succeeded',
  started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:00:05Z',
  asset_count: 3,
  software_count: 5,
  error_message: null,
  metadata: null,
  triggered_by_user_id: 1,
}

async function confirmIn(label: string) {
  const dialog = screen.getByRole('alertdialog')
  await act(async () => {
    fireEvent.click(within(dialog).getByRole('button', { name: label }))
  })
}

describe('IntegrationsPage focus after disconnect', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('disconnect success focuses Connect Microsoft 365', async () => {
    let resolveRefresh!: (v: unknown) => void
    mockFetchStatus
      .mockResolvedValueOnce(connected)
      .mockReturnValueOnce(new Promise((res) => { resolveRefresh = res }))
    mockDisconnect.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <IntegrationsPage />
      </MemoryRouter>,
    )
    const trigger = await screen.findByTestId('m365-disconnect')
    trigger.focus()
    fireEvent.click(trigger)
    await confirmIn('Disconnect')

    expect(screen.getByText('Loading…')).toBeInTheDocument()
    await act(async () => {})
    expect(screen.queryByRole('button', { name: 'Connect Microsoft 365' })).toBeNull()

    await act(async () => {
      resolveRefresh(notConnected)
    })

    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: 'Connect Microsoft 365' }),
      ),
    )
  })

  it('disconnect failure returns focus to Disconnect', async () => {
    mockFetchStatus.mockResolvedValue(connected)
    mockDisconnect.mockRejectedValue(new Error('nope'))
    render(
      <MemoryRouter>
        <IntegrationsPage />
      </MemoryRouter>,
    )
    const trigger = await screen.findByTestId('m365-disconnect')
    trigger.focus()
    fireEvent.click(trigger)
    await confirmIn('Disconnect')

    expect(await screen.findByText('nope')).toBeInTheDocument()
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId('m365-disconnect')))
    expect(screen.getByTestId('m365-disconnect')).toBeEnabled()
  })
})

describe('UploadInventoryPage focus after rollback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPreview.mockResolvedValue({
      valid_rows: 3,
      invalid_rows: [],
      distinct_assets: 3,
      distinct_software: 5,
      would_create: 3,
      would_update: 0,
    })
    mockImport.mockResolvedValue(run)
    mockGetRun.mockResolvedValue(run)
    mockGetDiff.mockResolvedValue(null)
  })

  async function reachUndo() {
    const { container } = render(
      <MemoryRouter>
        <UploadInventoryPage />
      </MemoryRouter>,
    )
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, {
      target: { files: [new File(['a,b'], 'inv.csv', { type: 'text/csv' })] },
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Preview' }))
    const importBtn = await screen.findByRole('button', { name: 'Import' })
    await waitFor(() => expect(importBtn).toBeEnabled())
    fireEvent.click(importBtn)
    return screen.findByRole('button', { name: 'Undo last upload' })
  }

  it('rollback success focuses Upload another', async () => {
    mockRollback.mockResolvedValue(undefined)
    const trigger = await reachUndo()
    trigger.focus()
    fireEvent.click(trigger)
    await confirmIn('Roll back')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Upload another' })),
    )
    expect(screen.queryByRole('button', { name: 'Undo last upload' })).toBeNull()
  })

  it('rollback failure returns focus to Undo last upload', async () => {
    mockRollback.mockRejectedValue(new Error('Rollback blew up'))
    const trigger = await reachUndo()
    trigger.focus()
    fireEvent.click(trigger)
    await confirmIn('Roll back')

    expect(await screen.findByText('Rollback blew up')).toBeInTheDocument()
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Undo last upload' })),
    )
    expect(screen.getByRole('button', { name: 'Undo last upload' })).toBeEnabled()
  })
})
