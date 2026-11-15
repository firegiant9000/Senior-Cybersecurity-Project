import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import DataHandlingPage from '../DataHandlingPage'

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: null }),
}))

vi.mock('../../hooks/useDataStatus', () => ({
  useDataStatus: () => ({ items: [], loading: false, error: null }),
}))

describe('DataHandlingPage', () => {
  it('explains how the dataset list stays in step with the dashboard without developer paths', () => {
    const { container } = render(
      <MemoryRouter>
        <DataHandlingPage />
      </MemoryRouter>,
    )

    expect(
      screen.getByText(
        /The list comes from a single registry that every dashboard widget must be listed in, and the badges you see on the dashboard read from that same registry\./,
      ),
    ).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/data_status\.py/)
    expect(container.textContent).not.toMatch(/\/api\/v1\//)
  })

  it('summarizes the logged-out readiness check without overclaiming', () => {
    render(
      <MemoryRouter>
        <DataHandlingPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Readiness check (no login)' })).toBeInTheDocument()
    expect(
      screen.getByText(
        /The domain is looked up in public DNS and is not stored or logged \(it is held in memory for up to 15 minutes to avoid repeat lookups\)\. Quiz answers are scored and not stored\./,
      ),
    ).toBeInTheDocument()
  })
})
