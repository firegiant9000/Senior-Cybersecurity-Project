import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Technology, Domains and Uploads pages, rendered inside the settings layout.
// Company and Security Profile: OrganisationPage.test.tsx.

const {
  mockListVendors,
  mockCreateVendor,
  mockDeleteVendor,
  mockListDomains,
  mockAddDomain,
  mockDeleteDomain,
  mockListUploads,
  mockUploadFile,
  mockDeleteUpload,
  authState,
} = vi.hoisted(() => ({
  mockListVendors: vi.fn(),
  mockCreateVendor: vi.fn(),
  mockDeleteVendor: vi.fn(),
  mockListDomains: vi.fn(),
  mockAddDomain: vi.fn(),
  mockDeleteDomain: vi.fn(),
  mockListUploads: vi.fn(),
  mockUploadFile: vi.fn(),
  mockDeleteUpload: vi.fn(),
  // useAuth() values are lower-cased by the real AuthContext.
  authState: {
    orgId: 1 as number | null,
    role: 'user' as string | null,
    orgRole: 'owner' as string | null,
  },
}))

// pages.tsx also imports the account section, which pulls in the Firebase client.
vi.mock('../../../firebase', () => ({ auth: { currentUser: null } }))

vi.mock('../../../api/fetchWithAuth', () => ({
  API_BASE_URL: 'http://api.test',
  fetchWithAuth: vi.fn(),
}))

vi.mock('../../../context/UserContext', () => ({
  useUserContext: () => ({
    organization: null,
    refreshOrganization: vi.fn(),
    loading: false,
    error: null,
  }),
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
  deleteVendor: mockDeleteVendor,
  importVendorsCsv: vi.fn(),
  previewVendorsCsv: vi.fn(),
  suggestVendors: vi.fn().mockResolvedValue([]),
  autocompleteVendors: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../../api/domains', () => ({
  listDomains: mockListDomains,
  addDomain: mockAddDomain,
  deleteDomain: mockDeleteDomain,
}))

vi.mock('../../../api/uploads', () => ({
  listUploads: mockListUploads,
  uploadFile: mockUploadFile,
  deleteUpload: mockDeleteUpload,
  downloadUpload: vi.fn(),
}))

import SettingsLayout from '../SettingsLayout'
import { DomainsPage, TechnologyPage, UploadsPage } from '../pages'

const ORG_ID = 1

function setup(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route element={<SettingsLayout />}>
          <Route path="/settings/technology" element={<TechnologyPage />} />
          <Route path="/settings/domains" element={<DomainsPage />} />
          <Route path="/settings/uploads" element={<UploadsPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

const emptyPage = { items: [], total: 0, page: 1, page_size: 20 }

beforeEach(() => {
  vi.clearAllMocks()
  authState.orgId = ORG_ID
  authState.role = 'user'
  authState.orgRole = 'owner'
  mockListVendors.mockResolvedValue(emptyPage)
  mockListDomains.mockResolvedValue(emptyPage)
  mockListUploads.mockResolvedValue(emptyPage)
  mockCreateVendor.mockResolvedValue({})
  mockDeleteVendor.mockResolvedValue(undefined)
  mockAddDomain.mockResolvedValue({})
  mockDeleteDomain.mockResolvedValue(undefined)
  mockUploadFile.mockResolvedValue({})
  mockDeleteUpload.mockResolvedValue(undefined)
})

describe('Technology page', () => {
  it('6. /settings/technology renders the Technology Stack section, listing vendors for the organisation', async () => {
    setup('/settings/technology')
    expect(screen.getByRole('heading', { level: 2, name: 'Your Technology Stack' })).toBeInTheDocument()
    expect(await screen.findByPlaceholderText('Vendor name')).toBeInTheDocument()
    await waitFor(() => expect(mockListVendors).toHaveBeenCalled())
    expect(mockListVendors.mock.calls[0][0]).toBe(ORG_ID)
    // The other org-data pages are not rendered here.
    expect(screen.queryByPlaceholderText('example.com')).toBeNull()
    expect(mockListDomains).not.toHaveBeenCalled()
    expect(mockListUploads).not.toHaveBeenCalled()
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
    setup('/settings/technology')

    fireEvent.change(await screen.findByPlaceholderText('Vendor name'), { target: { value: ' Fortinet ' } })
    fireEvent.change(screen.getByPlaceholderText('Product name (optional)'), { target: { value: 'FortiOS' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(mockCreateVendor).toHaveBeenCalledTimes(1))
    expect(mockCreateVendor).toHaveBeenCalledWith(ORG_ID, 'Fortinet', 'FortiOS')

    fireEvent.click(await screen.findByTitle('Remove'))
    await waitFor(() => expect(mockDeleteVendor).toHaveBeenCalledWith(ORG_ID, 11))
  })

  it('keeps an unsaved Technology draft while paging, and loads page 1 exactly once', async () => {
    mockListVendors.mockImplementation(async (_org: number, page: number) => ({
      items: [
        { id: page, vendor_name: `Vendor p${page}`, product_name: '', created_at: '2024-01-01T00:00:00Z', matched_kev_count: 0 },
      ],
      total: 40,
      page,
      page_size: 20,
    }))
    setup('/settings/technology')
    await screen.findByText('Vendor p1')
    expect(mockListVendors).toHaveBeenCalledTimes(1)
    fireEvent.change(screen.getByPlaceholderText('Vendor name'), { target: { value: 'Draft Vendor' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    await screen.findByText('Vendor p2')
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Vendor name')).toHaveValue('Draft Vendor')
    expect(mockListVendors).toHaveBeenCalledTimes(2)
  })

  it('renders nothing for the section without an organisation', async () => {
    authState.orgId = null
    authState.orgRole = null
    setup('/settings/technology')
    await screen.findByRole('heading', { level: 1, name: 'Settings' })
    expect(screen.queryByRole('heading', { name: 'Your Technology Stack' })).not.toBeInTheDocument()
    expect(mockListVendors).not.toHaveBeenCalled()
  })
})

describe('Domains page', () => {
  it('6b. /settings/domains renders the Organization Domains section, listing domains for the organisation', async () => {
    setup('/settings/domains')
    expect(screen.getByRole('heading', { level: 2, name: 'Organization Domains' })).toBeInTheDocument()
    expect(await screen.findByPlaceholderText('example.com')).toBeInTheDocument()
    await waitFor(() => expect(mockListDomains).toHaveBeenCalled())
    expect(mockListDomains.mock.calls[0][0]).toBe(ORG_ID)
    expect(screen.queryByPlaceholderText('Vendor name')).toBeNull()
    expect(mockListVendors).not.toHaveBeenCalled()
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
    setup('/settings/domains')

    fireEvent.change(await screen.findByPlaceholderText('example.com'), { target: { value: 'HTTPS://New.Example/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add Domain' }))
    await waitFor(() => expect(mockAddDomain).toHaveBeenCalledWith(ORG_ID, 'new.example'))

    fireEvent.click(await screen.findByTitle('Remove'))
    await waitFor(() => expect(mockDeleteDomain).toHaveBeenCalledWith(ORG_ID, 21))
  })
})

describe('Uploads page', () => {
  it('6c. /settings/uploads renders the File Uploads section, listing uploads for the organisation', async () => {
    setup('/settings/uploads')
    expect(screen.getByRole('heading', { level: 2, name: 'File Uploads' })).toBeInTheDocument()
    await waitFor(() => expect(mockListUploads).toHaveBeenCalled())
    expect(mockListUploads.mock.calls[0][0]).toBe(ORG_ID)
    expect(mockListVendors).not.toHaveBeenCalled()
    expect(mockListDomains).not.toHaveBeenCalled()
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
    setup('/settings/uploads')

    const file = new File(['a,b'], 'data.csv', { type: 'text/csv' })
    await screen.findByText('report.pdf')
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(mockUploadFile).toHaveBeenCalledWith(ORG_ID, file))
    expect(await screen.findByText('"data.csv" uploaded successfully')).toBeInTheDocument()

    fireEvent.click(await screen.findByTitle('Delete'))
    await waitFor(() => expect(mockDeleteUpload).toHaveBeenCalledWith(ORG_ID, 31))
  })
})
