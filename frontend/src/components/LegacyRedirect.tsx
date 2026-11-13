import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { resolveLegacyUrl } from '../config/redirects';
import NotFoundPage from '../pages/NotFoundPage';

export default function LegacyRedirect(): React.JSX.Element {
  const { pathname, search, hash } = useLocation();
  const target = resolveLegacyUrl(pathname, search, hash);
  if (target === null) return <NotFoundPage />;
  return <Navigate to={target} replace />;
}
