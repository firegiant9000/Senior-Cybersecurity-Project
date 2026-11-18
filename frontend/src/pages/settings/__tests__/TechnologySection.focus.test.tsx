import { useRef, type ComponentRef } from 'react'
import { render, screen, within, fireEvent, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockListVendors, mockDeleteVendor } = vi.hoisted(() => ({
  mockListVendors: vi.fn(),
  mockDeleteVendor: vi.fn(),
}))

vi.mock('../../../api/vendors', () => ({
  listVendors: (...args: unknown[]) => mockListVendors(...args),
  createVendor: vi.fn(),
  deleteVendor: (...args: unknown[]) => mockDeleteVendor(...args),
  importVendorsCsv: vi.fn(),
  previewVendorsCsv: vi.fn(),
  suggestVendors: vi.fn().mockResolvedValue([]),
  autocompleteVendors: vi.fn().mockResolvedValue([]),
}))

import TechnologySection from '../TechnologySection'

function vendor(id: number) {
  return {
    id,
    org_id: 1,
    vendor_name: `Vendor${id}`,
    product_name: `Product${id}`,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    matched_kev_count: 0,
  }
}

function page<T>(items: T[]) {
  return { total: items.length, page: 1, page_size: 20, items }
}

function Harness() {
  const ref = useRef<ComponentRef<'h2'>>(null)
  return (
    <section>
      <h2 ref={ref} tabIndex={-1}>Your Technology Stack</h2>
      <TechnologySection orgId={1} canEdit headingRef={ref} />
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

describe('TechnologySection focus after delete', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("focuses the next vendor's delete button once the reloaded list is shown", async () => {
    let resolveReload!: (v: unknown) => void
    mockListVendors
      .mockResolvedValueOnce(page([vendor(1), vendor(2), vendor(3)]))
      .mockReturnValueOnce(new Promise((res) => { resolveReload = res }))
    mockDeleteVendor.mockResolvedValue(undefined)
    render(<Harness />)
    await screen.findByRole('button', { name: 'Delete vendor Vendor1' })

    await confirmVia('Delete vendor Vendor1')

    expect(screen.getByText('Loading vendors...')).toBeInTheDocument()
    await act(async () => {})
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { name: 'Your Technology Stack' }))

    await act(async () => {
      resolveReload(page([vendor(2), vendor(3)]))
    })

    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: 'Delete vendor Vendor2' }),
      ),
    )
  })

  it("returns focus to the failed row's delete button even if the trigger was never focused", async () => {
    mockListVendors.mockResolvedValue(page([vendor(1), vendor(2)]))
    mockDeleteVendor.mockRejectedValue(new Error('nope'))
    render(<Harness />)
    await screen.findByRole('button', { name: 'Delete vendor Vendor1' })

    await confirmVia('Delete vendor Vendor1', { focusTrigger: false })

    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole('button', { name: 'Delete vendor Vendor1' }),
      ),
    )
  })
})
