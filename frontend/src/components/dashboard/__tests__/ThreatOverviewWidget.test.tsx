import { render, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ThreatOverviewWidget from '../ThreatOverviewWidget'
import type { DashboardData } from '../../../hooks/useDashboardData'

vi.mock('../../../api/ingest', () => ({
  fetchIngestFreshness: vi.fn().mockResolvedValue({ sources: [] }),
}))

vi.mock('../../shared/SourceBadge', () => ({
  default: (props: { datasetKey?: string; datasetKeys?: string[] }) => (
    <span
      data-testid="source-badge"
      data-dataset-key={props.datasetKeys ? props.datasetKeys.join(',') : props.datasetKey}
    />
  ),
}))

const data: DashboardData = {
  lossProjection: null,
  severityDistribution: [],
  kevTotal: 0,
  riskScoreStats: null,
}

describe('ThreatOverviewWidget source badge', () => {
  it('carries one badge for the nvd_cves, kev and risk_score datasets', async () => {
    const { container } = render(<ThreatOverviewWidget data={data} loading={false} />)
    await waitFor(() => expect(container.textContent).toContain('Last CVE ingest'))

    const badges = container.querySelectorAll('[data-testid="source-badge"]')
    expect(badges).toHaveLength(1)
    expect(badges[0]).toHaveAttribute('data-dataset-key', 'nvd_cves,kev,risk_score')
  })
})
