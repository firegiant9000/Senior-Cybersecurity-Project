import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DataSourcesTab from '../DataSourcesTab'

vi.mock('../../../firebase', () => ({
  auth: { currentUser: null },
}))
vi.mock('../IC3Table', () => ({ default: () => <div data-testid="ic3-table">IC3</div> }))
vi.mock('../EconomicsTable', () => ({ default: () => <div data-testid="economics-table">Economics</div> }))
vi.mock('../CisaKevTable', () => ({ default: () => <div data-testid="cisa-table">CISA</div> }))
vi.mock('../NvdTable', () => ({ default: () => <div data-testid="nvd-table">NVD</div> }))

describe('DataSourcesTab', () => {
  it('has no Domain Intelligence tab', async () => {
    render(<DataSourcesTab />)
    await screen.findByTestId('ic3-table')

    expect(screen.queryByRole('tab', { name: 'Domain Intelligence' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      'IC3 Incidents',
      'Economics',
      'CISA KEV',
      'NVD CVEs',
    ])
  })

  it('renders the IC3 table first', async () => {
    render(<DataSourcesTab />)

    expect(await screen.findByTestId('ic3-table')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'IC3 Incidents' })).toHaveAttribute('aria-selected', 'true')
  })

  it('no longer describes real-time reconnaissance', async () => {
    render(<DataSourcesTab />)
    await screen.findByTestId('ic3-table')

    expect(screen.queryByText(/Real-time/)).not.toBeInTheDocument()
  })
})
