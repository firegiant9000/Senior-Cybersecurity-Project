import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import App from './App'

// Mock the Dashboard component to avoid complex API dependencies
vi.mock('./Dashboard.tsx', () => ({
  default: () => <div data-testid="dashboard">Dashboard</div>,
}))

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByTestId('dashboard')).toBeInTheDocument()
  })
})
