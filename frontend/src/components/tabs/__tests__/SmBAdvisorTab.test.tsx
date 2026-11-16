import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi } from 'vitest'
import SmBAdvisorTab from '../SmBAdvisorTab'

const userContextValue = {
  organization: {
    name: 'Acme Ltd',
    industry_label: 'Finance',
    primary_state: 'CA',
    security_controls: { mfa_enabled: 'yes', edr_deployed: 'no' },
  },
}
vi.mock('../../../context/UserContext', () => ({
  useUserContext: () => userContextValue,
}))

vi.mock('../../../api/dashboardSummary', () => ({
  fetchIndustryRisk: () =>
    Promise.resolve({
      items: [{ sector: 'Finance', complaint_count: 10, total_loss: 1000, avg_loss_per_incident: 100 }],
      year: 2025,
    }),
  fetchAttackTypes: () => Promise.resolve({ items: [], year: 2025 }),
  fetchSectorAttackMatrix: () =>
    Promise.resolve({
      items: [
        {
          sector: 'Finance',
          attack_type: 'Business Email Compromise',
          complaint_count: 5,
          total_loss: 500,
          avg_loss_per_incident: 100,
        },
      ],
      year: 2025,
    }),
  fetchGeographicHeatmap: () =>
    Promise.resolve({
      items: [{ state: 'CA', complaint_count: 3, total_loss: 300, avg_loss_per_incident: 100 }],
      year: 2025,
    }),
}))

// A rejected score makes OrgRiskScoreCard render nothing, which is its designed fallback.
vi.mock('../../../api/smbRiskScore', () => ({
  fetchSmbRiskScore: () => Promise.reject(new Error('no org')),
}))

// The tab renders SourceBadges; the real hook imports firebase via fetchWithAuth.
vi.mock('../../../hooks/useDataStatus', () => ({
  useDataStatus: () => ({ byKey: {}, loading: false }),
}))

describe('SmBAdvisorTab Action Plan', () => {
  it('renders the Action Plan without checkboxes', async () => {
    render(
      <MemoryRouter>
        <SmBAdvisorTab />
      </MemoryRouter>,
    )

    // Wait for the industry-specific group, which needs the loaded matrix.
    await screen.findByText('Industry-Specific Threats')
    const card = screen.getByRole('heading', { name: /Your Action Plan/ }).closest('.smb-action-card')
    expect(card).not.toBeNull()
    const plan = within(card as HTMLElement)

    expect(plan.queryAllByRole('checkbox')).toHaveLength(0)
    expect(plan.getAllByRole('listitem').length).toBeGreaterThan(0)

    // Only the MFA item matches an enabled control (edr_deployed is 'no').
    const inPlace = plan.getAllByText('In place')
    expect(inPlace).toHaveLength(1)
    expect(inPlace[0].closest('li')).toHaveTextContent('multi-factor authentication')
  })
})
