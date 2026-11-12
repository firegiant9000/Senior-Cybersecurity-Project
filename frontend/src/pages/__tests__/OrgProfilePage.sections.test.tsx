import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Section state must survive collapsing and reopening an accordion section.

const {
  mockFetchWithAuth,
  mockRefreshOrganization,
  mockListVendors,
  mockCreateVendor,
  mockDeleteVendor,
  mockListDomains,
  mockAddDomain,
  mockDeleteDomain,
  mockListUploads,
  mockUploadFile,
  mockDeleteUpload,
  userContextState,
} = vi.hoisted(() => ({
  mockFetchWithAuth: vi.fn(),
  mockRefreshOrganization: vi.fn(),
  mockListVendors: vi.fn(),
  mockCreateVendor: vi.fn(),
  mockDeleteVendor: vi.fn(),
  mockListDomains: vi.fn(),
  mockAddDomain: vi.fn(),
  mockDeleteDomain: vi.fn(),
  mockListUploads: vi.fn(),
  mockUploadFile: vi.fn(),
  mockDeleteUpload: vi.fn(),
  userContextState: { value: {} as Record<string, unknown> },
}))

vi.mock('../../api/fetchWithAuth', () => ({
  API_BASE_URL: 'http://api.test',
  fetchWithAuth: mockFetchWithAuth,
}))

vi.mock('../../context/UserContext', () => ({
  useUserContext: () => userContextState.value,
}))

// ProtectedRoute (imported for canEditOrganizationProfile) pulls in AuthContext and firebase.
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { uid: 'u1', email: 'u@example.com' }, logout: vi.fn() }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../../api/vendors', () => ({
  listVendors: mockListVendors,
  createVendor: mockCreateVendor,
  deleteVendor: mockDeleteVendor,
  importVendorsCsv: vi.fn(),
  previewVendorsCsv: vi.fn(),
  suggestVendors: vi.fn().mockResolvedValue([]),
  autocompleteVendors: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../api/domains', () => ({
  listDomains: mockListDomains,
  addDomain: mockAddDomain,
  deleteDomain: mockDeleteDomain,
}))

vi.mock('../../api/uploads', () => ({
  listUploads: mockListUploads,
  uploadFile: mockUploadFile,
  deleteUpload: mockDeleteUpload,
  downloadUpload: vi.fn(),
}))

vi.mock('../../components/AssessmentReadiness', () => ({
  default: () => <div data-testid="readiness-widget" />,
}))

vi.mock('../../components/ValidationPanel', () => ({
  default: () => <div data-testid="validation-panel" />,
}))

import OrgProfilePage from '../OrgProfilePage'

const ORG_ID = 1

const baseOrg = {
  id: ORG_ID,
  name: 'Acme Corp',
  logo_url: 'https://acme.test/logo.png',
  primary_domain: 'acme.test',
  industry_label: 'Healthcare',
  security_controls: { mfa_enabled: 'yes' },
  cloud_providers: ['AWS', 'Azure'],
  compliance_frameworks: ['HIPAA'],
  data_types: ['PII (names, SSNs)'],
  device_count_range: '11-50',
  incident_history: 'none',
}

function makeProfile(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    email: 'u@example.com',
    is_active: true,
    role: 'user',
    auth_provider: 'password',
    created_at: '2024-01-01T00:00:00Z',
    org_id: ORG_ID,
    org_role: 'owner',
    ...overrides,
  }
}

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body, text: async () => JSON.stringify(body) }
}

let profile = makeProfile()

function setup(route = '/org-profile') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <OrgProfilePage />
    </MemoryRouter>,
  )
}

async function loaded(route?: string) {
  const utils = setup(route)
  await screen.findByLabelText('Name')
  return utils
}

function section(id: string) {
  const el = document.getElementById(id)
  if (!el) throw new Error(`missing #${id}`)
  return el
}

beforeEach(() => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  profile = makeProfile()
  userContextState.value = {
    organization: baseOrg,
    refreshOrganization: mockRefreshOrganization,
    loading: false,
    error: null,
  }
  mockRefreshOrganization.mockResolvedValue(undefined)
  mockFetchWithAuth.mockImplementation(async (url: string, init?: { method?: string }) => {
    if (url.endsWith('/api/v1/auth/me')) return jsonResponse(profile)
    if (init?.method === 'PUT') return jsonResponse({})
    return jsonResponse({})
  })
  mockListVendors.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  mockListDomains.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  mockListUploads.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  mockCreateVendor.mockResolvedValue({})
  mockDeleteVendor.mockResolvedValue(undefined)
  mockAddDomain.mockResolvedValue({})
  mockDeleteDomain.mockResolvedValue(undefined)
  mockUploadFile.mockResolvedValue({})
  mockDeleteUpload.mockResolvedValue(undefined)
})


describe('OrgProfilePage section state survives collapse', () => {
  it('keeps an unsaved Company edit after collapsing and reopening', async () => {
    await loaded()
    // Wait for the section's sync-from-organisation effect before editing.
    await waitFor(() => expect(screen.getByLabelText('Name')).toHaveValue('Acme Corp'))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Draft Name' } })
    const header = screen.getByRole('button', { name: /^Company profile/ })
    fireEvent.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByLabelText('Name')).toHaveValue('Draft Name')
  })

  it('keeps an unsaved Security Profile edit after collapsing and reopening', async () => {
    await loaded()
    const header = screen.getByRole('button', { name: /^Security Profile/ })
    fireEvent.click(header)
    const sec = within(section('section-security-profile'))
    const gcp = sec.getByLabelText('GCP')
    await waitFor(() => expect(sec.getByLabelText('AWS')).toBeChecked())
    expect(gcp).not.toBeChecked()
    fireEvent.click(gcp)
    fireEvent.click(header)
    fireEvent.click(header)
    expect(within(section('section-security-profile')).getByLabelText('GCP')).toBeChecked()
  })

  it('keeps an unsaved Technology draft and the current page after collapsing and reopening', async () => {
    mockListVendors.mockImplementation(async (_org: number, page: number) => ({
      items: [
        { id: page, vendor_name: `Vendor p${page}`, product_name: '', created_at: '2024-01-01T00:00:00Z', matched_kev_count: 0 },
      ],
      total: 40,
      page,
      page_size: 20,
    }))
    await loaded()
    const header = screen.getByRole('button', { name: /^Your Technology Stack/ })
    fireEvent.click(header)
    const tech = within(section('section-vendors'))
    await tech.findByText('Vendor p1')
    // The initial load fetches page 1 exactly once.
    expect(mockListVendors).toHaveBeenCalledTimes(1)
    fireEvent.change(tech.getByPlaceholderText('Vendor name'), { target: { value: 'Draft Vendor' } })
    fireEvent.click(tech.getByRole('button', { name: 'Next' }))
    await tech.findByText('Vendor p2')
    fireEvent.click(header)
    fireEvent.click(header)
    const reopened = within(section('section-vendors'))
    expect(reopened.getByPlaceholderText('Vendor name')).toHaveValue('Draft Vendor')
    expect(reopened.getByText('Page 2 of 2')).toBeInTheDocument()
    // Collapsing and reopening does not refetch.
    expect(mockListVendors).toHaveBeenCalledTimes(2)
  })

  it('keeps an unsaved Domains draft after collapsing and reopening', async () => {
    await loaded()
    const header = screen.getByRole('button', { name: /^Organization Domains/ })
    fireEvent.click(header)
    const dom = within(section('section-domains'))
    fireEvent.change(dom.getByPlaceholderText('example.com'), { target: { value: 'draft.example' } })
    fireEvent.click(header)
    expect(header).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(header)
    expect(within(section('section-domains')).getByPlaceholderText('example.com')).toHaveValue('draft.example')
  })

  it('keeps the Uploads success banner after collapsing and reopening', async () => {
    await loaded()
    const header = screen.getByRole('button', { name: /^File Uploads/ })
    fireEvent.click(header)
    const input = section('section-uploads').querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['a,b'], 'data.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [file] } })
    await within(section('section-uploads')).findByText('"data.csv" uploaded successfully')
    fireEvent.click(header)
    fireEvent.click(header)
    expect(
      within(section('section-uploads')).getByText('"data.csv" uploaded successfully'),
    ).toBeInTheDocument()
  })

  it('returns Technology to page 1 and reloads once when cloud providers sync', async () => {
    mockListVendors.mockImplementation(async (_org: number, page: number) => ({
      items: [
        { id: page, vendor_name: `Vendor p${page}`, product_name: '', created_at: '2024-01-01T00:00:00Z', matched_kev_count: 0 },
      ],
      total: 40,
      page,
      page_size: 20,
    }))
    await loaded()
    fireEvent.click(screen.getByRole('button', { name: /^Your Technology Stack/ }))
    const tech = within(section('section-vendors'))
    await tech.findByText('Vendor p1')
    fireEvent.click(tech.getByRole('button', { name: 'Next' }))
    await tech.findByText('Vendor p2')
    expect(mockListVendors).toHaveBeenCalledTimes(2)

    fireEvent.click(screen.getByRole('button', { name: /^Security Profile/ }))
    fireEvent.click(within(section('section-security-profile')).getByRole('button', { name: 'Save security profile' }))
    await tech.findByText('Vendor p1')
    expect(tech.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(mockCreateVendor).toHaveBeenCalled()
    expect(mockListVendors).toHaveBeenCalledTimes(3)
  })
})
