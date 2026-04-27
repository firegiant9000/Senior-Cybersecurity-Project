import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

/**
 * Aligns with backend ``PUT /organizations/{org_id}``: global ``role === "admin"``
 * or org-level ``org_role`` of ``owner`` / ``admin`` (API uses lowercase strings).
 */
export function canEditOrganizationProfile(
  userRole: string | null | undefined,
  orgRole: string | null | undefined,
): boolean {
  if ((userRole ?? "").toLowerCase() === "admin") return true;
  const r = (orgRole ?? "").toLowerCase();
  return r === "admin" || r === "owner";
}

export default function ProtectedRoute({ children, requireOrg = true }: { children: React.ReactNode; requireOrg?: boolean }) {
  const { user, loading, orgId, orgLoading, profileError, refreshProfile, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (loading || orgLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <p>Loading...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/" replace />;
  }

  // If profile fetch failed, show error instead of wrongly redirecting
  if (profileError) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", flexDirection: "column", gap: "1rem" }}>
        <p>Failed to load your profile. Please check your connection.</p>
        <button onClick={() => refreshProfile()} style={{ padding: "0.5rem 1rem", cursor: "pointer" }}>
          Retry
        </button>
        <button onClick={async () => { await logout(); navigate("/"); }} style={{ padding: "0.5rem 1rem", cursor: "pointer", opacity: 0.7 }}>
          Log Out
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
