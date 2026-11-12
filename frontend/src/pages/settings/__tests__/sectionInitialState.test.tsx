import { useLayoutEffect } from 'react'
import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import CompanySection from '../CompanySection'
import SecurityProfileSection from '../SecurityProfileSection'

const organization = {
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

vi.mock('../../../context/UserContext', () => ({
  useUserContext: () => ({
    organization,
    refreshOrganization: vi.fn(),
    loading: false,
    error: null,
  }),
}))
vi.mock('../../../api/organizations', () => ({ updateOrganization: vi.fn() }))
vi.mock('../../../api/vendors', () => ({ createVendor: vi.fn() }))

// A layout effect in a later sibling runs after the first commit but before any
// passive effect. That is the window in which a fast edit (or a test typing as soon
// as the field appears) used to be overwritten by the sync-from-organization effect.
function ProbeFirstCommit({ id, onRead }: { id: string; onRead: (value: string) => void }) {
  useLayoutEffect(() => {
    const el = document.getElementById(id) as HTMLInputElement | HTMLSelectElement | null
    onRead(el?.value ?? '<missing>')
  }, [id, onRead])
  return null
}

describe('organisation sections render organisation values on their first commit', () => {
  it('CompanySection', () => {
    const reads: string[] = []
    render(
      <>
        <CompanySection orgId={7} canEdit onChanged={() => {}} />
        <ProbeFirstCommit id="company-name" onRead={(v) => reads.push(v)} />
      </>,
    )
    expect(reads[0]).toBe('Acme Corp')
  })

  it('SecurityProfileSection', () => {
    const reads: string[] = []
    render(
      <>
        <SecurityProfileSection orgId={7} canEdit onChanged={() => {}} onVendorsSynced={() => {}} />
        <ProbeFirstCommit id="device-count" onRead={(v) => reads.push(v)} />
      </>,
    )
    expect(reads[0]).toBe('11-50')
  })
})
