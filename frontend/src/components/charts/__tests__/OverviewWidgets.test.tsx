import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { AttackTypeStats, IndustryRiskProfile } from '../../../api/dashboardSummary';
import LossByAttackTypeChart from '../LossByAttackTypeChart';
import SectorImpactTable from '../SectorImpactTable';

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 800, height: 400 }}>{children}</div>
    ),
  };
});

const attackTypes = [
  { attack_type: 'Phishing', total_loss: 5000, complaint_count: 3 },
] as unknown as AttackTypeStats[];

const sectors = [
  { sector: 'Healthcare', complaint_count: 1200, total_loss: 2500000, avg_loss_per_incident: 2083 },
] as unknown as IndustryRiskProfile[];

describe('LossByAttackTypeChart', () => {
  it('shows a skeleton and no empty message while loading', () => {
    const { container } = render(<LossByAttackTypeChart data={[]} loading />);
    expect(screen.getByText('Total Financial Loss by Attack Type')).toBeInTheDocument();
    expect(screen.queryByText('No data available.')).toBeNull();
    expect(container.querySelector('.card')).not.toBeNull();
  });

  it('shows the empty message with no data', () => {
    render(<LossByAttackTypeChart data={[]} loading={false} />);
    expect(screen.getByText('No data available.')).toBeInTheDocument();
  });

  it('renders the heading and IC3 badge with data', () => {
    render(<LossByAttackTypeChart data={attackTypes} loading={false} />);
    expect(screen.getByText('Total Financial Loss by Attack Type')).toBeInTheDocument();
    expect(screen.getByText(/Victim Financial Impact/)).toBeInTheDocument();
  });
});

describe('SectorImpactTable', () => {
  it('shows no rows while loading', () => {
    render(<SectorImpactTable data={sectors} loading />);
    expect(screen.getByText('Sector Impact Summary')).toBeInTheDocument();
    expect(screen.queryByText('Healthcare')).toBeNull();
  });

  it('renders sector rows', () => {
    render(<SectorImpactTable data={sectors} loading={false} />);
    expect(screen.getByText('Healthcare')).toBeInTheDocument();
    expect(screen.getByText('$2,500,000')).toBeInTheDocument();
  });
});
