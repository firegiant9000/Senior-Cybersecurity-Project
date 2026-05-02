import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';

const { mockNavigate } = vi.hoisted(() => ({ mockNavigate: vi.fn() }));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

import GlossaryPage from '../GlossaryPage';
import { getGlossaryEntries } from '../../components/shared/InfoTip';

describe('GlossaryPage', () => {
  it('renders all glossary entries alphabetically', () => {
    render(
      <MemoryRouter>
        <GlossaryPage />
      </MemoryRouter>
    );

    const entries = getGlossaryEntries();
    expect(entries.length).toBeGreaterThan(0);

    for (const { term } of entries) {
      expect(screen.getByText(term)).toBeInTheDocument();
    }

    expect(screen.getByText('CVE')).toBeInTheDocument();
    expect(screen.getByText('KEV')).toBeInTheDocument();
    expect(screen.getByText('ANOMALY')).toBeInTheDocument();
    expect(screen.getByText('VENDOR ALERT')).toBeInTheDocument();
    expect(screen.getByText('RISK SCORE')).toBeInTheDocument();
  });

  it('renders the Back to Dashboard button and navigates on click', () => {
    render(
      <MemoryRouter>
        <GlossaryPage />
      </MemoryRouter>
    );

    const backBtn = screen.getByRole('button', { name: /back to dashboard/i });
    expect(backBtn).toBeInTheDocument();

    fireEvent.click(backBtn);
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });
});
