import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Characterisation tests: pin the current behaviour of OrgProfilePage so it can
// be split into section components without changing what users and the API see.

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
  await screen.findByLabelText(/^Company Name/)
  return utils
}

function putCalls() {
  return mockFetchWithAuth.mock.calls.filter(([, init]) => init?.method === 'PUT')
}

function section(id: string) {
  const el = document.getElementById(id)
  if (!el) throw new Error(`missing #${id}`)
  return el
}

async function openSection(titlePattern: RegExp, id: string) {
  fireEvent.click(await screen.findByRole('button', { name: titlePattern }))
  return section(id)
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

describe('OrgProfilePage characterisation', () => {
  it('1a. owner sees Company fields enabled and the Security Profile section', async () => {
    await loaded()
    expect(screen.getByLabelText(/^Company Name/)).toBeEnabled()
    expect(screen.getByLabelText('Logo')).toBeEnabled()
    expect(screen.getByLabelText(/^Primary Domain/)).toBeEnabled()
    expect(screen.getByLabelText(/^Industry/)).toBeEnabled()
    expect(screen.getByLabelText(/^Primary State/)).toBeEnabled()
    expect(screen.getByLabelText(/^Number of Employees/)).toBeEnabled()
    expect(screen.getByLabelText(/^Annual Revenue/)).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Save company profile' })).toBeInTheDocument()
    expect(document.getElementById('section-security-profile')).not.toBeNull()
  })

  it('1b. member sees Company fields disabled and no Security Profile section', async () => {
    profile = makeProfile({ org_role: 'member' })
    await loaded()
    expect(screen.getByLabelText(/^Company Name/)).toBeDisabled()
    expect(screen.getByLabelText('Logo')).toBeDisabled()
    expect(screen.getByLabelText(/^Primary Domain/)).toBeDisabled()
    expect(screen.getByLabelText(/^Industry/)).toBeDisabled()
    expect(screen.getByLabelText(/^Primary State/)).toBeDisabled()
    expect(screen.getByLabelText(/^Number of Employees/)).toBeDisabled()
    expect(screen.getByLabelText(/^Annual Revenue/)).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save company profile' })).not.toBeInTheDocument()
    expect(document.getElementById('section-security-profile')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Save security profile' })).not.toBeInTheDocument()
  })

  it('1c. has an h1, an Account Settings link and no Back to Dashboard control', async () => {
    await loaded()
    expect(screen.getByRole('heading', { level: 1, name: 'Organization Profile' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Account Settings' })).toHaveAttribute('href', '/settings/account')
    expect(screen.queryByText(/Back to Dashboard/i)).not.toBeInTheDocument()
  })

  it('2. saving Company sends exactly its seven fields, null for each empty value', async () => {
    await loaded()
    fireEvent.change(screen.getByLabelText(/^Company Name/), { target: { value: '  Acme Ltd  ' } })
    fireEvent.change(screen.getByLabelText('Logo'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText(/^Primary Domain/), { target: { value: 'acme.example' } })
    fireEvent.change(screen.getByLabelText(/^Industry/), { target: { value: 'Education' } })
    fireEvent.change(screen.getByLabelText(/^Primary State/), { target: { value: 'TX' } })
    fireEvent.change(screen.getByLabelText(/^Number of Employees/), { target: { value: '11-50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save company profile' }))

    await waitFor(() => expect(putCalls()).toHaveLength(1))
    const [url, init] = putCalls()[0]
    expect(url).toBe(`http://api.test/api/v1/organizations/${ORG_ID}`)
    expect(JSON.parse(init.body)).toEqual({
      name: 'Acme Ltd',
      logo_url: null,
      primary_domain: 'acme.example',
      industry_label: 'Education',
      primary_state: 'TX',
      employee_range: '11-50',
      revenue_range: null,
    })
    expect(Object.keys(JSON.parse(init.body)).sort()).toEqual(
      [
        'employee_range',
        'industry_label',
        'logo_url',
        'name',
        'primary_domain',
        'primary_state',
        'revenue_range',
      ],
    )
    await waitFor(() => expect(mockRefreshOrganization).toHaveBeenCalledTimes(2)) // mount + after save
  })

  it('2b. an organisation loaded with primary_state TX shows it selected', async () => {
    userContextState.value = {
      ...userContextState.value,
      organization: { ...baseOrg, primary_state: 'TX', employee_range: '51-200', revenue_range: '$1M-$5M' },
    }
    await loaded()
    expect(screen.getByLabelText(/^Primary State/)).toHaveValue('TX')
    expect(screen.getByLabelText(/^Number of Employees/)).toHaveValue('51-200')
    expect(screen.getByLabelText(/^Annual Revenue/)).toHaveValue('$1M-$5M')
  })

  it('2c. Security Profile compliance options include Unsure and None clears the others', async () => {
    await loaded()
    const sec = await openSection(/Security Profile/, 'section-security-profile')
    expect(within(sec).getByLabelText('Unsure')).not.toBeChecked()
    expect(within(sec).getByLabelText('HIPAA')).toBeChecked()
    fireEvent.click(within(sec).getByLabelText('None'))
    expect(within(sec).getByLabelText('None')).toBeChecked()
    expect(within(sec).getByLabelText('HIPAA')).not.toBeChecked()
    // a framework after "None" clears "None"
    fireEvent.click(within(sec).getByLabelText('HIPAA'))
    expect(within(sec).getByLabelText('HIPAA')).toBeChecked()
    expect(within(sec).getByLabelText('None')).not.toBeChecked()
    // "Unsure" after a framework clears the framework
    fireEvent.click(within(sec).getByLabelText('Unsure'))
    expect(within(sec).getByLabelText('Unsure')).toBeChecked()
    expect(within(sec).getByLabelText('HIPAA')).not.toBeChecked()
  })

  it('3. saving Security Profile sends exactly its six fields, then createVendor per cloud provider', async () => {
    await loaded()
    const sec = await openSection(/Security Profile/, 'section-security-profile')
    fireEvent.click(within(sec).getByLabelText('GCP'))
    fireEvent.click(within(sec).getByLabelText('Azure')) // uncheck
    fireEvent.change(within(sec).getByLabelText('Approximate device count'), { target: { value: '51-200' } })
    fireEvent.click(within(sec).getAllByRole('button', { name: 'No' })[0]) // first control -> no
    fireEvent.click(within(sec).getByRole('button', { name: 'Save security profile' }))

    await waitFor(() => expect(putCalls()).toHaveLength(1))
    const [url, init] = putCalls()[0]
    expect(url).toBe(`http://api.test/api/v1/organizations/${ORG_ID}`)
    const body = JSON.parse(init.body)
    expect(Object.keys(body).sort()).toEqual(
      [
        'cloud_providers',
        'compliance_frameworks',
        'data_types',
        'device_count_range',
        'incident_history',
        'security_controls',
      ],
    )
    expect(body).toEqual({
      security_controls: { mfa_enabled: 'no' },
      cloud_providers: ['AWS', 'GCP'],
      compliance_frameworks: ['HIPAA'],
      data_types: ['PII (names, SSNs)'],
      device_count_range: '51-200',
      incident_history: 'none',
    })

    await waitFor(() => expect(mockCreateVendor).toHaveBeenCalledTimes(2))
    expect(mockCreateVendor).toHaveBeenCalledWith(ORG_ID, 'AWS', '', { idempotent: true })
    expect(mockCreateVendor).toHaveBeenCalledWith(ORG_ID, 'GCP', '', { idempotent: true })
  })

  it('4. listVendors, listDomains and listUploads are called with the organisation id', async () => {
    await loaded()
    await waitFor(() => {
      expect(mockListVendors).toHaveBeenCalled()
      expect(mockListDomains).toHaveBeenCalled()
      expect(mockListUploads).toHaveBeenCalled()
    })
    expect(mockListVendors.mock.calls[0][0]).toBe(ORG_ID)
    expect(mockListDomains.mock.calls[0][0]).toBe(ORG_ID)
    expect(mockListUploads.mock.calls[0][0]).toBe(ORG_ID)
  })

  it('5a. adding and deleting a vendor call createVendor and deleteVendor', async () => {
    mockListVendors.mockResolvedValue({
      items: [
        {
          id: 11, org_id: ORG_ID, vendor_name: 'Cisco', product_name: 'IOS',
          created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z', matched_kev_count: 0,
        },
      ],
      total: 1, page: 1, page_size: 20,
    })
    await loaded()
    const sec = await openSection(/Technology Stack/, 'section-vendors')

    fireEvent.change(within(sec).getByPlaceholderText('Vendor name'), { target: { value: ' Fortinet ' } })
    fireEvent.change(within(sec).getByPlaceholderText('Product name (optional)'), { target: { value: 'FortiOS' } })
    fireEvent.click(within(sec).getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(mockCreateVendor).toHaveBeenCalledTimes(1))
    expect(mockCreateVendor).toHaveBeenCalledWith(ORG_ID, 'Fortinet', 'FortiOS')

    fireEvent.click(await within(sec).findByTitle('Remove'))
    await waitFor(() => expect(mockDeleteVendor).toHaveBeenCalledWith(ORG_ID, 11))
  })

  it('5b. adding and deleting a domain call addDomain and deleteDomain', async () => {
    mockListDomains.mockResolvedValue({
      items: [
        {
          id: 21, org_id: ORG_ID, domain_name: 'old.example', is_verified: false, added_by: null,
          created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 1, page: 1, page_size: 20,
    })
    await loaded()
    const sec = await openSection(/Organization Domains/, 'section-domains')

    fireEvent.change(within(sec).getByPlaceholderText('example.com'), { target: { value: 'HTTPS://New.Example/path' } })
    fireEvent.click(within(sec).getByRole('button', { name: 'Add Domain' }))
    await waitFor(() => expect(mockAddDomain).toHaveBeenCalledWith(ORG_ID, 'new.example'))

    fireEvent.click(await within(sec).findByTitle('Remove'))
    await waitFor(() => expect(mockDeleteDomain).toHaveBeenCalledWith(ORG_ID, 21))
  })

  it('5c. uploading and deleting a file call uploadFile and deleteUpload', async () => {
    mockListUploads.mockResolvedValue({
      items: [
        {
          id: 31, org_id: ORG_ID, uploaded_by: null, original_filename: 'report.pdf',
          stored_filename: 'x', file_size_bytes: 2048, content_type: 'application/pdf',
          upload_purpose: null, created_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 1, page: 1, page_size: 20,
    })
    await loaded()
    const sec = await openSection(/File Uploads/, 'section-uploads')

    const file = new File(['a,b'], 'data.csv', { type: 'text/csv' })
    const input = sec.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(mockUploadFile).toHaveBeenCalledWith(ORG_ID, file))

    fireEvent.click(await within(sec).findByTitle('Delete'))
    await waitFor(() => expect(mockDeleteUpload).toHaveBeenCalledWith(ORG_ID, 31))
  })

  it('6. rendering at /settings/technology opens the Technology Stack section', async () => {
    await loaded('/settings/technology')
    const sec = section('section-vendors')
    await waitFor(() =>
      expect(within(sec).getByPlaceholderText('Vendor name')).toBeInTheDocument(),
    )
    expect(within(sec).getByRole('button', { name: /Technology Stack/ })).toHaveAttribute('aria-expanded', 'true')
    // other sections stay closed
    expect(within(section('section-domains')).queryByPlaceholderText('example.com')).toBeNull()
  })

  it('7a. the readiness widget renders when org_id is set', async () => {
    await loaded()
    expect(screen.getByTestId('readiness-widget')).toBeInTheDocument()
  })

  it('7b. the readiness widget and org sections do not render without an org', async () => {
    profile = makeProfile({ org_id: null, org_role: null })
    setup()
    await screen.findByText(/not part of an organization yet/i)
    expect(screen.queryByTestId('readiness-widget')).not.toBeInTheDocument()
    expect(document.getElementById('section-vendors')).toBeNull()
  })
})
