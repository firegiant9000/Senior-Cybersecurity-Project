import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AssessmentReadinessWidget from '../AssessmentReadiness'
import type { AssessmentReadiness } from '../../api/assessmentReadiness'

const { mockNavigate, mockFetchReadiness } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockFetchReadiness: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../api/assessmentReadiness', () => ({
  fetchAssessmentReadiness: mockFetchReadiness,
}))

const readiness: AssessmentReadiness = {
  is_ready: false,
  readiness_pct: 20,
  tier: 'minimal',
  next_steps: [],
  items: [
    { key: 'vendors', label: 'Vendors', complete: false, required: true, detail: '' },
    { key: 'security_controls', label: 'Security controls', complete: false, required: true, detail: '' },
  ],
}

function renderWidget() {
  return render(
    <MemoryRouter>
      <AssessmentReadinessWidget />
    </MemoryRouter>,
  )
}

function fixButtonFor(label: string) {
  const row = (screen.getByText(label)).closest('.readiness-item') as HTMLElement
  return within(row).getByRole('button', { name: 'Fix' })
}

describe('AssessmentReadiness Fix links', () => {
  beforeEach(() => {
    mockNavigate.mockReset()
    mockFetchReadiness.mockReset()
    mockFetchReadiness.mockResolvedValue(readiness)
  })

  it('vendors Fix goes to the technology settings', async () => {
    renderWidget()
    await waitFor(() => expect(screen.getByText('Vendors')).toBeInTheDocument())

    fireEvent.click(fixButtonFor('Vendors'))

    expect(mockNavigate).toHaveBeenCalledWith('/settings/technology')
  })

  it('security controls Fix goes to the security profile section of organisation settings', async () => {
    renderWidget()
    await waitFor(() => expect(screen.getByText('Security controls')).toBeInTheDocument())

    fireEvent.click(fixButtonFor('Security controls'))

    expect(mockNavigate).toHaveBeenCalledWith('/settings/organisation#security-profile')
  })
})
