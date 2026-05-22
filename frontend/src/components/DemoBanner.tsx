import { useAuth } from "../context/AuthContext";

/**
 * Renders a sticky banner when the signed-in user's organisation is flagged
 * `is_demo`. Suppressed until auth has finished resolving so users never see
 * a flash of "real" state before the banner appears.
 */
export function DemoBanner() {
  const { loading, orgLoading, orgId, orgIsDemo } = useAuth();

  if (loading || orgLoading) return null;
  if (orgId === null) return null;
  if (!orgIsDemo) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        background: "#fff7ed",
        color: "#9a3412",
        borderBottom: "1px solid #fdba74",
        padding: "8px 16px",
        fontSize: "0.875rem",
        fontWeight: 500,
        textAlign: "center",
      }}
    >
      Demo organisation — data is illustrative and not pulled from your real
      tenant. Switch to a production org to see live data.
    </div>
  );
}

export default DemoBanner;
