import React from 'react';
import { useAuth } from '../context/AuthContext';
import { isPlatformAdmin } from '../utils/roleUtils';
import NotFoundPage from '../pages/NotFoundPage';

export default function RequirePlatformAdmin({ children }: { children: React.ReactNode }): React.JSX.Element {
  const { role } = useAuth();
  if (!isPlatformAdmin(role ?? null)) return <NotFoundPage embedded />;
  return <>{children}</>;
}
