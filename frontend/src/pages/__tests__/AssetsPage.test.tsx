import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'

import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AssetsPage from '../AssetsPage'

const {
  mockListAssets,
  mockGetAsset,
  mockGetAssetFindings,
  mockGetAssetRiskSummary,
  mockGetInventoryHealth,
  mockPatchFindingStatus,
  mockSetAssetTags,
} = vi.hoisted(() => ({
  mockListAssets: vi.fn(),
  mockGetAsset: vi.fn(),
  mockGetAssetFindings: vi.fn(),
  mockGetAssetRiskSummary: vi.fn(),
  mockGetInventoryHealth: vi.fn(),
  mockPatchFindingStatus: vi.fn(),
  mockSetAssetTags: vi.fn(),
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ orgId: 7 }),
}))

vi.mock('../../api/assets', () => ({
  listAssets: mockListAssets,
  getAsset: mockGetAsset,
  getAssetFindings: mockGetAssetFindings,
  getAssetRiskSummary: mockGetAssetRiskSummary,
  getInventoryHealth: mockGetInventoryHealth,
  patchAssetFindingStatus: mockPatchFindingStatus,
  setAssetTags: mockSetAssetTags,
}))

vi.mock('../../components/shared/SourceBadge', () => ({
  default: ({ datasetKey }: { datasetKey: string }) => (
    <span data-testid="source-badge" data-dataset-key={datasetKey} />
  ),
}))

const makeAsset = (id: number, hostname: string) => ({
  id,
  org_id: 7,
  hostname,
  ip_address: '10.0.0.5',
  os_name: 'Windows',
  os_version: '11',
  mac_address: null,
  discovered_via: 'csv_upload',
  first_seen: '2026-01-01T00:00:00Z',
  last_seen: '2026-01-02T00:00:00Z',
  is_active: true,
  metadata: null,
  tags: [],
  created_by_scan_run_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  source: 'csv_upload',
})

const finding = {
  finding_id: 99,
  software_id: 1,
  vendor: 'Acme',
  product: 'Widget',
  version: '1.2.3',
  cve_id: 'CVE-2026-1111',
  cvss_score: 9.8,
  epss_score: 0.5,
  severity: 'critical',
  in_kev: true,
  match_confidence: 'high',
  risk_score: 90,
  risk_tier: 'Critical',
  status: 'open',
  remediation_summary: null,
  description: null,
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AssetsPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockListAssets.mockResolvedValue({
    total: 2,
    page: 1,
    page_size: 50,
    items: [
      { asset: makeAsset(1, 'alpha-host'), kev_match_count: 3 },
      { asset: makeAsset(2, 'beta-host'), kev_match_count: 0 },
    ],
  })
  mockGetAsset.mockResolvedValue({
    asset: makeAsset(1, 'alpha-host'),
    software: [
      { id: 1, asset_id: 1, org_id: 7, vendor: 'Acme', product: 'Widget', version: '1.2.3' },
    ],
    services: [],
    listening_ports: [],
  })
  mockGetAssetFindings.mockResolvedValue({
    asset_id: 1,
    total: 1,
    items: [finding],
    note: 'Preliminary matches',
  })
  mockGetAssetRiskSummary.mockResolvedValue({ org_id: 7, items: [], note: '', source: 'x' })
  mockGetInventoryHealth.mockResolvedValue({
    assets_total: 2,
    assets_with_known_software: 1,
    assets_with_kev_match: 1,
    last_inventory_update: null,
    last_source: null,
    top_vendors: [],
    source: 'x',
  })
  mockPatchFindingStatus.mockResolvedValue({ status: 'false_positive' })
})

describe('AssetsPage source badges', () => {
  it('labels the inventory and the KEV matches column with their sources', async () => {
    const { container } = renderPage()
    await screen.findByText('alpha-host')

    const inventory = container.querySelector('[data-dataset-key="assets_inventory"]')
    expect(inventory).toBeInTheDocument()
    const h1 = screen.getByRole('heading', { level: 1, name: 'Assets' })
    expect(inventory?.closest('h1')).toBeNull()
    expect(inventory?.parentElement).toBe(h1.parentElement)

    const kev = container.querySelector('[data-dataset-key="asset_kev_matches"]')
    expect(kev).toBeInTheDocument()
    expect(kev?.closest('th')).toBeNull()
    expect(screen.getByRole('columnheader', { name: 'KEV matches' })).toBeInTheDocument()
  })

  it('keeps the inventory badge when the inventory is empty', async () => {
    mockListAssets.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] })
    const { container } = renderPage()
    await screen.findByText(/No assets yet/)

    const inventory = container.querySelector('[data-dataset-key="assets_inventory"]')
    expect(inventory).toBeInTheDocument()
    const h1 = screen.getByRole('heading', { level: 1, name: 'Assets' })
    expect(inventory?.parentElement).toBe(h1.parentElement)
    expect(container.querySelector('[data-dataset-key="asset_kev_matches"]')).toBeNull()
  })

  it('shows no badges when the inventory fails to load', async () => {
    mockListAssets.mockRejectedValue(new Error('boom'))
    const { container } = renderPage()
    await screen.findByText('boom')

    expect(container.querySelector('[data-dataset-key="assets_inventory"]')).toBeNull()
    expect(container.querySelector('[data-dataset-key="asset_kev_matches"]')).toBeNull()
  })

  it('shows no badges while the inventory is loading', () => {
    mockListAssets.mockReturnValue(new Promise(() => {}))
    mockGetInventoryHealth.mockReturnValue(new Promise(() => {}))
    mockGetAssetRiskSummary.mockReturnValue(new Promise(() => {}))
    const { container } = renderPage()
    expect(container.querySelector('[data-dataset-key]')).toBeNull()
  })
})

describe('AssetsPage (characterisation)', () => {
  it('lists assets from the API for the current organisation', async () => {
    renderPage()
    expect(await screen.findByText('alpha-host')).toBeInTheDocument()
    expect(screen.getByText('beta-host')).toBeInTheDocument()
    expect(mockListAssets).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ page: 1, pageSize: 50 }),
    )
  })

  it('the Upload CSV link points at /org/assets/upload', async () => {
    renderPage()
    await screen.findByText('alpha-host')
    expect(screen.getByRole('link', { name: 'Upload CSV' })).toHaveAttribute(
      'href',
      '/org/assets/upload',
    )
  })

  it('opening an asset shows its software and CVE matches', async () => {
    renderPage()
    await screen.findByText('alpha-host')
    fireEvent.click(screen.getAllByRole('button', { name: 'View' })[0])

    expect(await screen.findByRole('heading', { name: 'Software (1)' })).toBeInTheDocument()
    expect(await screen.findByText('CVE-2026-1111')).toBeInTheDocument()
    expect(mockGetAsset).toHaveBeenCalledWith(7, 1)
    expect(mockGetAssetFindings).toHaveBeenCalledWith(7, 1)
    expect(screen.getByRole('heading', { name: /CVE matches\s+\(1\)/ })).toBeInTheDocument()
    // Software table row
    const softwareHeading = screen.getByRole('heading', { name: 'Software (1)' })
    const softwareTable = softwareHeading.nextElementSibling as HTMLElement
    expect(within(softwareTable).getByText('Widget')).toBeInTheDocument()
    expect(within(softwareTable).getByText('1.2.3')).toBeInTheDocument()
  })

  it('"Report false positive" calls the status API with false_positive', async () => {
    renderPage()
    await screen.findByText('alpha-host')
    fireEvent.click(screen.getAllByRole('button', { name: 'View' })[0])
    fireEvent.click(await screen.findByRole('button', { name: 'Report false positive' }))

    expect(mockPatchFindingStatus).toHaveBeenCalledTimes(1)
    expect(mockPatchFindingStatus).toHaveBeenCalledWith(7, 1, 99, 'false_positive')
    // The server's status is shown afterwards, with an undo control.
    expect(await screen.findByRole('button', { name: 'Undo' })).toBeInTheDocument()
  })

  it('the empty state links to the upload page', async () => {
    mockListAssets.mockResolvedValue({ total: 0, page: 1, page_size: 50, items: [] })
    renderPage()
    const link = await screen.findByRole('link', { name: 'Upload a CSV' })
    expect(link).toHaveAttribute('href', '/org/assets/upload')
    await waitFor(() => expect(screen.queryByText('alpha-host')).not.toBeInTheDocument())
  })
})
