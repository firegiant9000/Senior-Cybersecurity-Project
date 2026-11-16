import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi } from 'vitest'
import UploadInventoryPage from '../UploadInventoryPage'

const { mockPreview, mockImport, mockDiff, mockGetRun, mockRollback } = vi.hoisted(() => ({
  mockPreview: vi.fn(),
  mockImport: vi.fn(),
  mockDiff: vi.fn(),
  mockGetRun: vi.fn(),
  mockRollback: vi.fn(),
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ orgId: 7 }),
}))

vi.mock('../../api/inventory', () => ({
  previewInventoryCsv: mockPreview,
  importInventoryCsv: mockImport,
  getScanRunDiff: mockDiff,
  getScanRun: mockGetRun,
  rollbackScanRun: mockRollback,
}))

vi.mock('../../api/analytics', () => ({
  logActivationEvent: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../hooks/useDataStatus', () => ({
  useDataStatus: () => ({ byKey: {}, loading: false }),
}))

describe('UploadInventoryPage source badge', () => {
  it('labels the last-upload heading with the scan_runs data source', async () => {
    mockPreview.mockResolvedValue({
      valid_rows: 1,
      distinct_assets: 1,
      distinct_software: 1,
      would_create: 1,
      would_update: 0,
      invalid_rows: [],
    })
    mockImport.mockResolvedValue({
      id: 42,
      status: 'succeeded',
      asset_count: 1,
      software_count: 1,
      error_message: null,
      metadata: null,
    })
    mockDiff.mockResolvedValue(null)

    const { container } = render(
      <MemoryRouter>
        <UploadInventoryPage />
      </MemoryRouter>,
    )

    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['hostname\nh1'], 'inv.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Preview' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Import' }))

    const heading = await screen.findByRole('heading', { name: /Import #42/ })
    const badge = heading.querySelector('[data-dataset-key="scan_runs"]')
    expect(badge).not.toBeNull()
  })
})
