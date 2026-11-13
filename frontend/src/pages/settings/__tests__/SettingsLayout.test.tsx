import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SettingsLayout from '../SettingsLayout';

const EXPECTED = [
  ['Account', '/settings/account'],
  ['Organisation', '/settings/organisation'],
  ['Technology stack', '/settings/technology'],
  ['Domains', '/settings/domains'],
  ['File uploads', '/settings/uploads'],
  ['Team', '/settings/team'],
  ['Scanner agents', '/settings/agents'],
  ['Integrations', '/settings/integrations'],
];

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={['/settings/domains']}>
      <Routes>
        <Route path="/settings" element={<SettingsLayout />}>
          <Route path="domains" element={<div>domains marker</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('SettingsLayout', () => {
  it('renders the heading and the child route', () => {
    renderLayout();
    expect(screen.getByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument();
    expect(screen.getByText('domains marker')).toBeInTheDocument();
  });

  it('renders the eight menu links in order with the current one marked', () => {
    renderLayout();
    const links = within(screen.getByRole('navigation', { name: 'Settings' })).getAllByRole('link');
    expect(links.map((l) => [l.textContent, l.getAttribute('href')])).toEqual(EXPECTED);
    for (const link of links) {
      if (link.textContent === 'Domains') {
        expect(link).toHaveAttribute('aria-current', 'page');
      } else {
        expect(link).not.toHaveAttribute('aria-current');
      }
    }
  });
});
