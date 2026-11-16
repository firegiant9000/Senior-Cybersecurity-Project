import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import UploadInventoryPage from '../UploadInventoryPage'

const { mockPreview, mockImport, mockRollback, mockGetRun, mockGetDiff } = vi.hoisted(() => ({
  mockPreview: vi.fn(),
  mockImport: vi.fn(),
  mockRollback: vi.fn(),
  mockGetRun: vi.fn(),
  mockGetDiff: vi.fn(),
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ orgId: 7 }),
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

// The page renders a SourceBadge; the real hook imports firebase via fetchWithAuth.
vi.mock('../../hooks/useDataStatus', () => ({
  useDataStatus: () => ({ byKey: {}, loading: false }),
}))

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

async function importFile() {
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
  fireEvent.click(await screen.findByRole('button', { name: 'Undo last upload' }))
  return screen.findByRole('alertdialog')
}

describe('UploadInventoryPage rollback confirm', () => {
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
    mockRollback.mockResolvedValue(undefined)
  })

  it('shows the dialog and makes no call on Cancel', async () => {
    const dialog = await importFile()
    expect(within(dialog).getByText('Roll back import')).toBeInTheDocument()
    expect(
      within(dialog).getByText('Remove the assets and software entries this upload created? Assets that already existed and were updated by it keep those updates.'),
    ).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })
    expect(mockRollback).not.toHaveBeenCalled()
  })

  it('rolls back once on Confirm', async () => {
    const dialog = await importFile()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Roll back' }))
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })
    expect(mockRollback).toHaveBeenCalledTimes(1)
    expect(mockRollback).toHaveBeenCalledWith(7, 42)
    expect(await screen.findByText(/Rolled back\./)).toBeInTheDocument()
  })

  it('closes the dialog and shows the error when the API rejects', async () => {
    mockRollback.mockRejectedValue(new Error('Rollback blew up'))
    const dialog = await importFile()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Roll back' }))
    await waitFor(() => {
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    })
    expect(await screen.findByText('Rollback blew up')).toBeInTheDocument()
  })
})
