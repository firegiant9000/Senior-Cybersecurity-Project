import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Company, Security Profile, readiness and validation behaviour of OrganisationPage,
// rendered inside the settings layout. Technology, Domains and Uploads: OrgDataPages.test.tsx.

const {
  mockFetchWithAuth,
  mockRefreshOrganization,
  mockListVendors,
  mockCreateVendor,
  authState,
  userContextState,
} = vi.hoisted(() => ({
  mockFetchWithAuth: vi.fn(),
  mockRefreshOrganization: vi.fn(),
  mockListVendors: vi.fn(),
  mockCreateVendor: vi.fn(),
  // useAuth() values are lower-cased by the real AuthContext.
  authState: {
    orgId: 1 as number | null,
    role: 'user' as string | null,
    orgRole: 'owner' as string | null,
  },
  userContextState: { value: {} as Record<string, unknown> },
}))

// pages.tsx also imports the account section, which pulls in the Firebase client.
vi.mock('../../../firebase', () => ({ auth: { currentUser: null } }))

vi.mock('../../../api/fetchWithAuth', () => ({
  API_BASE_URL: 'http://api.test',
  fetchWithAuth: mockFetchWithAuth,
}))

vi.mock('../../../context/UserContext', () => ({
  useUserContext: () => userContextState.value,
}))

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { uid: 'u1', email: 'u@example.com' },
    orgId: authState.orgId,
    role: authState.role,
    orgRole: authState.orgRole,
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../../../api/vendors', () => ({
  listVendors: mockListVendors,
  createVendor: mockCreateVendor,
  deleteVendor: vi.fn(),
  importVendorsCsv: vi.fn(),
  previewVendorsCsv: vi.fn(),
  suggestVendors: vi.fn().mockResolvedValue([]),
  autocompleteVendors: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../../components/AssessmentReadiness', () => ({
  default: ({ refreshKey }: { refreshKey?: number }) => (
    <div data-testid="readiness-widget" data-refresh-key={refreshKey} />
  ),
}))

vi.mock('../../../components/ValidationPanel', () => ({
  default: () => <div data-testid="validation-panel" />,
}))

import SettingsLayout from '../SettingsLayout'
import { OrganisationPage } from '../pages'

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

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: async () => body, text: async () => JSON.stringify(body) }
}

function setup(route = '/settings/organisation') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route element={<SettingsLayout />}>
          <Route path="/settings/organisation" element={<OrganisationPage />} />
        </Route>
      </Routes>
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

function securitySection() {
  const el = document.getElementById('security-profile')
  if (!el) throw new Error('missing #security-profile')
  return el
}

beforeEach(() => {
  vi.clearAllMocks()
  Element.prototype.scrollIntoView = vi.fn()
  authState.orgId = ORG_ID
  authState.role = 'user'
  authState.orgRole = 'owner'
  userContextState.value = {
    organization: baseOrg,
    refreshOrganization: mockRefreshOrganization,
    loading: false,
    error: null,
  }
  mockRefreshOrganization.mockResolvedValue(undefined)
  mockFetchWithAuth.mockImplementation(async () => jsonResponse({}))
  mockListVendors.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
  mockCreateVendor.mockResolvedValue({})
})

describe('OrganisationPage', () => {
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
    expect(document.getElementById('security-profile')).not.toBeNull()
  })

  it('1b. member sees Company fields disabled and no Security Profile section', async () => {
    authState.orgRole = 'member'
    await loaded()
    expect(screen.getByLabelText(/^Company Name/)).toBeDisabled()
    expect(screen.getByLabelText('Logo')).toBeDisabled()
    expect(screen.getByLabelText(/^Primary Domain/)).toBeDisabled()
    expect(screen.getByLabelText(/^Industry/)).toBeDisabled()
    expect(screen.getByLabelText(/^Primary State/)).toBeDisabled()
    expect(screen.getByLabelText(/^Number of Employees/)).toBeDisabled()
    expect(screen.getByLabelText(/^Annual Revenue/)).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Save company profile' })).not.toBeInTheDocument()
    expect(document.getElementById('security-profile')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Save security profile' })).not.toBeInTheDocument()
  })

  it('1c. has the Settings h1, the Company profile h2, an Account link and no Back to Dashboard control', async () => {
    await loaded()
    expect(screen.getByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Company profile' })).toBeInTheDocument()
    expect(within(screen.getByRole('navigation', { name: 'Settings' })).getByRole('link', { name: 'Account' })).toHaveAttribute(
      'href',
      '/settings/account',
    )
    expect(screen.queryByText(/Back to Dashboard/i)).not.toBeInTheDocument()
  })

  it('1d. a non-admin (role user, org role member) sees no Security Profile section and no edit controls', async () => {
    authState.role = 'user'
    authState.orgRole = 'member'
    await loaded()
    expect(document.getElementById('security-profile')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Security Profile' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save company profile' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save security profile' })).not.toBeInTheDocument()
    expect(screen.getByLabelText(/^Company Name/)).toBeDisabled()
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
    const sec = securitySection()
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
    const sec = securitySection()
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

  it('6. /settings/organisation#security-profile scrolls the section into view', async () => {
    const scrolled: Element[] = []
    Element.prototype.scrollIntoView = vi.fn(function (this: Element) {
      scrolled.push(this)
    })
    await loaded('/settings/organisation#security-profile')
    await waitFor(() => expect(scrolled).toContain(securitySection()))
  })

  it('6b. without the hash nothing is scrolled', async () => {
    await loaded('/settings/organisation')
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
  })

  it('6c. scrolls exactly once even when a Company save replaces the organisation', async () => {
    await loaded('/settings/organisation#security-profile')
    await waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1))

    // The save refreshes UserContext, which hands the page a new organization object.
    mockRefreshOrganization.mockImplementation(async () => {
      userContextState.value = { ...userContextState.value, organization: { ...baseOrg, name: 'Acme Ltd' } }
    })
    mockRefreshOrganization.mockClear()
    fireEvent.change(screen.getByLabelText(/^Company Name/), { target: { value: 'Acme Ltd' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save company profile' }))

    await waitFor(() => expect(putCalls()).toHaveLength(1))
    await waitFor(() => expect(mockRefreshOrganization).toHaveBeenCalledTimes(1))
    expect(userContextState.value.organization).toEqual({ ...baseOrg, name: 'Acme Ltd' })
    // The page re-renders with the new organisation once the save bumps the readiness key.
    await waitFor(() => expect(screen.getByTestId('readiness-widget')).toHaveAttribute('data-refresh-key', '1'))
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1)
  })

  it('7a. the readiness widget and validation panel render when org_id is set', async () => {
    await loaded()
    expect(screen.getByTestId('readiness-widget')).toBeInTheDocument()
    expect(screen.getByTestId('validation-panel')).toBeInTheDocument()
  })

  it('7b. the readiness widget, validation panel and org sections do not render without an org', async () => {
    authState.orgId = null
    authState.orgRole = null
    setup()
    await screen.findByRole('heading', { level: 1, name: 'Settings' })
    expect(screen.queryByTestId('readiness-widget')).not.toBeInTheDocument()
    expect(screen.queryByTestId('validation-panel')).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^Company Name/)).not.toBeInTheDocument()
    expect(document.getElementById('security-profile')).toBeNull()
  })
})
