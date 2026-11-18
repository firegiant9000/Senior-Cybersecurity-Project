import { useRef, type ComponentRef } from 'react'
import { render, screen, within, fireEvent, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockListDomains, mockDeleteDomain, mockListUploads, mockDeleteUpload } = vi.hoisted(() => ({
  mockListDomains: vi.fn(),
  mockDeleteDomain: vi.fn(),
  mockListUploads: vi.fn(),
  mockDeleteUpload: vi.fn(),
}))

vi.mock('../../../api/domains', () => ({
  listDomains: (...args: unknown[]) => mockListDomains(...args),
  addDomain: vi.fn(),
  deleteDomain: (...args: unknown[]) => mockDeleteDomain(...args),
}))

vi.mock('../../../api/uploads', () => ({
  listUploads: (...args: unknown[]) => mockListUploads(...args),
  uploadFile: vi.fn(),
  deleteUpload: (...args: unknown[]) => mockDeleteUpload(...args),
  downloadUpload: vi.fn(),
}))

import DomainsSection from '../DomainsSection'
import UploadsSection from '../UploadsSection'

function domain(id: number) {
  return {
    id,
    org_id: 1,
    domain_name: `site${id}.example.com`,
    is_verified: false,
    added_by: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }
}

function upload(id: number) {
  return {
    id,
    org_id: 1,
    uploaded_by: null,
    original_filename: `file${id}.csv`,
    stored_filename: `stored${id}`,
    file_size_bytes: 100,
    content_type: 'text/csv',
    upload_purpose: null,
    created_at: '2024-01-01T00:00:00Z',
  }
}

function page<T>(items: T[]) {
  return { total: items.length, page: 1, page_size: 20, items }
}

function DomainsHarness() {
  const ref = useRef<ComponentRef<'h2'>>(null)
  return (
    <section>
      <h2 ref={ref} tabIndex={-1}>Organization Domains</h2>
      <DomainsSection open orgId={1} canEdit onChanged={vi.fn()} headingRef={ref} />
    </section>
  )
}

function UploadsHarness() {
  const ref = useRef<ComponentRef<'h2'>>(null)
  return (
    <section>
      <h2 ref={ref} tabIndex={-1}>File Uploads</h2>
      <UploadsSection open orgId={1} canEdit onChanged={vi.fn()} headingRef={ref} />
    </section>
  )
}

async function confirmVia(triggerName: string, { focusTrigger = true } = {}) {
  const trigger = screen.getByRole('button', { name: triggerName })
  // Safari does not focus a button on mouse click; focusTrigger=false models that.
  if (focusTrigger) trigger.focus()
  fireEvent.click(trigger)
  const dialog = screen.getByRole('alertdialog')
  await act(async () => {
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }))
  })
}

describe('DomainsSection focus after delete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("focuses the next domain's delete button once the reloaded list is shown", async () => {
    let resolveReload!: (v: unknown) => void
    mockListDomains
      .mockResolvedValueOnce(page([domain(1), domain(2), domain(3)]))
      .mockReturnValueOnce(new Promise((res) => { resolveReload = res }))
    mockDeleteDomain.mockResolvedValue(undefined)
    render(<DomainsHarness />)
    await screen.findByRole('button', { name: 'Delete domain site1.example.com' })

    await confirmVia('Delete domain site1.example.com')

    expect(screen.getByText('Loading domains...')).toBeInTheDocument()
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { name: 'Organization Domains' }))

    await act(async () => {
      resolveReload(page([domain(2), domain(3)]))
    })

    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: 'Delete domain site2.example.com' }),
      ),
    )
  })

  it('focuses the heading when the last domain is deleted', async () => {
    mockListDomains
      .mockResolvedValueOnce(page([domain(1)]))
      .mockResolvedValue(page([]))
    mockDeleteDomain.mockResolvedValue(undefined)
    render(<DomainsHarness />)
    await screen.findByRole('button', { name: 'Delete domain site1.example.com' })

    await confirmVia('Delete domain site1.example.com')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Organization Domains' })),
    )
  })

  it("returns focus to the failed row's delete button even if the trigger was never focused", async () => {
    mockListDomains.mockResolvedValue(page([domain(1), domain(2)]))
    mockDeleteDomain.mockRejectedValue(new Error('nope'))
    render(<DomainsHarness />)
    await screen.findByRole('button', { name: 'Delete domain site1.example.com' })

    await confirmVia('Delete domain site1.example.com', { focusTrigger: false })

    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: 'Delete domain site1.example.com' }),
      ),
    )
  })
})

describe('UploadsSection focus after delete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("focuses the next upload's delete button after deleting", async () => {
    mockListUploads
      .mockResolvedValueOnce(page([upload(1), upload(2)]))
      .mockResolvedValue(page([upload(2)]))
    mockDeleteUpload.mockResolvedValue(undefined)
    render(<UploadsHarness />)
    await screen.findByRole('button', { name: 'Delete upload file1.csv' })

    await confirmVia('Delete upload file1.csv')

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Delete upload file2.csv' })),
    )
  })

  it("returns focus to the failed row's delete button even if the trigger was never focused", async () => {
    mockListUploads.mockResolvedValue(page([upload(1), upload(2)]))
    mockDeleteUpload.mockRejectedValue(new Error('nope'))
    render(<UploadsHarness />)
    await screen.findByRole('button', { name: 'Delete upload file1.csv' })

    await confirmVia('Delete upload file1.csv', { focusTrigger: false })

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Delete upload file1.csv' })),
    )
  })
})
