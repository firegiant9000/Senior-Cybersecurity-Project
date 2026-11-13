import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { resolveLegacyUrl } from '../config/redirects';
import NotFoundPage from '../pages/NotFoundPage';

export default function LegacyRedirect(): React.JSX.Element {
  const { pathname, search, hash } = useLocation();
  // React Router matches case-insensitively and ignores a trailing slash; resolveLegacyUrl is exact.
  const normalised = pathname.replace(/\/+$/, '').toLowerCase() || '/';
  const target = resolveLegacyUrl(normalised, search, hash);
  if (target === null) return <NotFoundPage />;
  return <Navigate to={target} replace />;
}
