import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

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

  it('renders a Glossary h1 and no Back to Dashboard button (the shell provides navigation)', () => {
    render(
      <MemoryRouter>
        <GlossaryPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Glossary' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /back to dashboard/i })).not.toBeInTheDocument();
  });
});
