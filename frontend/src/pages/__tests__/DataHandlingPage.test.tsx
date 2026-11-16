import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
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
        /\(the quiz is not available yet\)\. The domain is looked up in public DNS and is not saved or logged \(the result is reused for up to 15 minutes to avoid repeat lookups\)\. Quiz answers are scored and not saved\. The only thing saved to the database is an anonymous count of each step per day\. Your IP address appears in the server's request logs and is used for rate limiting, as on every request\./,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/nothing about the visitor/)).toBeNull()
  })
})
