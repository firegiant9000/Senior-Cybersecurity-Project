import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Returns true if the user's global role + org role allows editing
 * the organization profile (name, logo, domain).
 */
export function canEditOrganizationProfile(
  globalRole: string | null | undefined,
  orgRole: string | null | undefined,
): boolean {
  if (globalRole === "admin") return true;
  return orgRole === "owner" || orgRole === "admin";
}

export default function ProtectedRoute({ children, requireOrg = true }: { children: React.ReactNode; requireOrg?: boolean }) {
  const { user, loading, orgId, orgLoading, profileError, refreshProfile } = useAuth();
  const location = useLocation();

  if (loading || orgLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // If profile fetch failed, show error instead of wrongly redirecting
  if (profileError) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", flexDirection: "column", gap: "1rem" }}>
        <p>Failed to load your profile. Please check your connection.</p>
        <button onClick={() => refreshProfile()} style={{ padding: "0.5rem 1rem", cursor: "pointer" }}>
          Retry
        </button>
      </div>
    );
  }

  // Redirect users without an org to onboarding (unless already there)
  if (requireOrg && orgId === null && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}
