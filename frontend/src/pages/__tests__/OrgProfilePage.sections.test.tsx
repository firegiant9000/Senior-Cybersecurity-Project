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
})
