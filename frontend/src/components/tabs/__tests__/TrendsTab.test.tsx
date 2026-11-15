import { render } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import TrendsTab from '../TrendsTab'

vi.mock('../../../firebase', () => ({
  auth: { currentUser: null },
}))

vi.mock('../../../hooks/useTrendsData', () => ({
  useTrendsData: () => ({
    data: {
      trends: [],
      attackTypeOptions: [],
      selectedAttackType: undefined,
      selectedSector: undefined,
      yearFrom: undefined,
      yearTo: undefined,
    },
    loading: false,
    errors: [],
    setAttackType: vi.fn(),
    setSector: vi.fn(),
    setYearFrom: vi.fn(),
    setYearTo: vi.fn(),
    refresh: vi.fn(),
    setOnProgress: vi.fn(),
  }),
}))

vi.mock('../../intel/IncidentLandscape', () => ({
  default: () => <div data-testid="incident-landscape" />,
}))

vi.mock('../../shared/SourceBadge', () => ({
  default: ({ datasetKey }: { datasetKey: string }) => (
    <span data-testid="source-badge" data-dataset-key={datasetKey} />
  ),
}))

describe('TrendsTab source badges', () => {
  it('labels each of the four yearly-trend cards with ic3_temporal_trends', () => {
    const { container } = render(<TrendsTab />)

    const cards = container.querySelectorAll('.trends-grid > *')
    expect(cards).toHaveLength(4)
    cards.forEach((card) => {
      const badges = card.querySelectorAll('[data-testid="source-badge"]')
      expect(badges).toHaveLength(1)
      expect(badges[0]).toHaveAttribute('data-dataset-key', 'ic3_temporal_trends')
    })
  })
})
