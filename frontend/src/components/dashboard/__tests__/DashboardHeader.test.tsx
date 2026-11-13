import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import DashboardHeader from '../DashboardHeader';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ role: null, orgRole: 'member' }),
}));

describe('DashboardHeader avatar menu', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('links Integrations from the avatar menu', () => {
    render(
      <DashboardHeader
        dark={false}
        onToggleDark={() => {}}
        user={{ email: 'member@example.com' }}
        onLogout={async () => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Integrations' }));

    expect(mockNavigate).toHaveBeenCalledWith('/settings/integrations');
  });
});
