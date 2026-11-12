import { useLayoutEffect, useRef } from 'react'
import { render, fireEvent } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import CompanySection from '../CompanySection'
import SecurityProfileSection from '../SecurityProfileSection'

const ctx = vi.hoisted(() => ({ organization: null as Record<string, unknown> | null }))

vi.mock('../../../context/UserContext', () => ({
  useUserContext: () => ({
    organization: ctx.organization,
    refreshOrganization: vi.fn(),
    loading: false,
    error: null,
  }),
}))
vi.mock('../../../api/organizations', () => ({ updateOrganization: vi.fn() }))
vi.mock('../../../api/vendors', () => ({ createVendor: vi.fn() }))

function makeOrg() {
  return {
    id: 7,
    name: 'Acme Corp',
    logo_url: null,
    primary_domain: 'acme.example',
    industry_label: 'Education',
    security_controls: {},
    cloud_providers: ['aws'],
    compliance_frameworks: [],
    data_types: [],
    device_count_range: '11-50',
    incident_history: null,
  }
}

// A layout effect in a later sibling runs after a commit and before any passive
// effect. It records the field's value in the first commit where the field exists.
// If that value is stale, a user edit made before a passive sync effect flushes
// would be overwritten by it, which is the bug this guards against.
function ReadOnFirstCommit({ id, reads }: { id: string; reads: string[] }) {
  const done = useRef(false)
  useLayoutEffect(() => {
    if (done.current) return
    const el = document.getElementById(id) as unknown as { value: string } | null
    if (!el) return
    done.current = true
    reads.push(el.value)
  })
  return null
}

function company(reads: string[]) {
  return (
    <>
      <CompanySection orgId={7} canEdit onChanged={() => {}} />
      <ReadOnFirstCommit id="company-name" reads={reads} />
    </>
  )
}

function security(reads: string[]) {
  return (
    <>
      <SecurityProfileSection orgId={7} canEdit onChanged={() => {}} onVendorsSynced={() => {}} />
      <ReadOnFirstCommit id="device-count" reads={reads} />
    </>
  )
}

function field(id: string) {
  return document.getElementById(id) as unknown as { value: string }
}

beforeEach(() => {
  ctx.organization = null
})

describe('organisation fields hold organisation values from the first commit that shows them', () => {
  it('CompanySection, organisation loaded before mount', () => {
    ctx.organization = makeOrg()
    const reads: string[] = []
    render(company(reads))
    expect(reads).toEqual(['Acme Corp'])
  })

  it('CompanySection, organisation arrives after mount', () => {
    const reads: string[] = []
    const { rerender } = render(company(reads))
    expect(reads).toEqual([]) // no field until the organisation loads
    ctx.organization = makeOrg()
    rerender(company(reads))
    expect(reads).toEqual(['Acme Corp'])
  })

  // No "arrives after mount" case for SecurityProfileSection: it renders its fields
  // without an organisation, and the page mounts it only once one is loaded.
  it('SecurityProfileSection, organisation loaded before mount', () => {
    ctx.organization = makeOrg()
    const reads: string[] = []
    render(security(reads))
    expect(reads).toEqual(['11-50'])
  })

  it('keeps an edit while the organisation object is unchanged', () => {
    ctx.organization = makeOrg()
    const { rerender } = render(<CompanySection orgId={7} canEdit onChanged={() => {}} />)
    fireEvent.change(field('company-name'), { target: { value: 'Draft' } })
    rerender(<CompanySection orgId={7} canEdit onChanged={() => {}} />)
    expect(field('company-name').value).toBe('Draft')
  })

  it('re-syncs the fields when a different organisation object arrives', () => {
    ctx.organization = makeOrg()
    const { rerender } = render(<CompanySection orgId={7} canEdit onChanged={() => {}} />)
    fireEvent.change(field('company-name'), { target: { value: 'Draft' } })
    ctx.organization = { ...makeOrg(), name: 'Acme Renamed' }
    rerender(<CompanySection orgId={7} canEdit onChanged={() => {}} />)
    expect(field('company-name').value).toBe('Acme Renamed')
  })
})
