import { render, screen, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import DataSourcesTab from '../DataSourcesTab'

vi.mock('../../../firebase', () => ({
  auth: { currentUser: null },
}))
vi.mock('../IC3Table', () => ({ default: () => <div data-testid="ic3-table">IC3</div> }))
vi.mock('../EconomicsTable', () => ({ default: () => <div data-testid="economics-table">Economics</div> }))

function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
      <Routes>
        <Route path="/intel/reference/:dataset" element={<DataSourcesTab />} />
        <Route path="/intel/vulnerabilities" element={<div data-testid="vulnerabilities">Vulnerabilities</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DataSourcesTab', () => {
  it('has no Domain Intelligence tab', async () => {
    renderAt('/intel/reference/ic3')
    await screen.findByTestId('ic3-table')

    const nav = screen.getByRole('navigation', { name: 'Reference datasets' })
    expect(within(nav).queryByRole('link', { name: 'Domain Intelligence' })).not.toBeInTheDocument()
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'IC3 Incidents',
      'Economics',
    ])
  })

  it('renders the IC3 table first', async () => {
    renderAt('/intel/reference/ic3')

    expect(await screen.findByTestId('ic3-table')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'IC3 Incidents' })).toHaveAttribute('aria-current', 'page')
  })

  it('no longer describes real-time reconnaissance', async () => {
    renderAt('/intel/reference/ic3')
    await screen.findByTestId('ic3-table')

    expect(screen.queryByText(/Real-time/)).not.toBeInTheDocument()
  })

  it('renders the economics stub at /intel/reference/economics', async () => {
    renderAt('/intel/reference/economics')

    expect(await screen.findByTestId('economics-table')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/intel/reference/economics')
    expect(screen.getByRole('link', { name: 'Economics' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'IC3 Incidents' })).not.toHaveAttribute('aria-current')
  })

  it('sends /intel/reference/cisa to the KEV view on Vulnerabilities', async () => {
    renderAt('/intel/reference/cisa')

    expect(await screen.findByTestId('vulnerabilities')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/intel/vulnerabilities?source=kev')
  })

  it('sends /intel/reference/nvd to the NVD view on Vulnerabilities', async () => {
    renderAt('/intel/reference/nvd')

    expect(await screen.findByTestId('vulnerabilities')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/intel/vulnerabilities?source=nvd')
  })

  it('sends an unknown dataset to /intel/reference/ic3', async () => {
    renderAt('/intel/reference/zzz')

    expect(await screen.findByTestId('ic3-table')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/intel\/reference\/ic3$/)
  })
})
