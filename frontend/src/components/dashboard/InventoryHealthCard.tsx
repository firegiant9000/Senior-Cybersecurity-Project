import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { API_BASE_URL, fetchWithAuth } from "../../api/fetchWithAuth";
import SourceBadge from "../shared/SourceBadge";

/**
 * Month 2 Phase F3: Inventory health summary card on the overview tab.
 *
 * Renders only when the user has an org. Pulls from
 * GET /api/v1/organizations/{org_id}/inventory/health which returns
 * asset totals, KEV-match count, and the timestamp of the most recent
 * scan_run.
 */

interface InventoryHealth {
  assets_total: number;
  assets_with_known_software: number;
  assets_with_kev_match: number;
  last_inventory_update: string | null;
  last_source: string | null;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diffSec = Math.round((Date.now() - then) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.round(diffSec / 3600)}h ago`;
  return `${Math.round(diffSec / 86400)}d ago`;
}

export default function InventoryHealthCard() {
  const { orgId } = useAuth();
  const [data, setData] = useState<InventoryHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!orgId) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    fetchWithAuth(
      `${API_BASE_URL}/api/v1/organizations/${orgId}/inventory/health`,
      { signal: controller.signal },
    )
      .then(async (resp) => {
        if (!resp.ok) {
          throw new Error(`Inventory health failed: ${resp.status}`);
        }
        return resp.json();
      })
      .then((j: InventoryHealth) => setData(j))
      .catch((e) => {
        if ((e as Error).name !== "AbortError") setError((e as Error).message);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [orgId]);

  if (!orgId) return null;

  return (
    <div className="card" style={{ position: "relative" }}>
      <span className="widget-title">Inventory Health</span>
      {loading ? (
        <p style={{ color: "var(--text-muted, #6b7280)", fontSize: 13 }}>Loading…</p>
      ) : error ? (
        <p style={{ color: "#991b1b", fontSize: 13 }}>{error}</p>
      ) : data == null ? null : (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 12,
              marginTop: 8,
            }}
          >
            <Metric label="Assets" value={data.assets_total} color="#3f51b5" />
            <Metric
              label="With software"
              value={data.assets_with_known_software}
              color="#0ea5e9"
            />
            <Metric
              label="KEV matches"
              value={data.assets_with_kev_match}
              color={data.assets_with_kev_match > 0 ? "#dc2626" : "#64748b"}
            />
          </div>
          <div
            style={{
              marginTop: 12,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: 12,
              color: "var(--text-muted, #64748b)",
            }}
          >
            <span>
              {data.last_inventory_update
                ? `Last upload: ${relativeTime(data.last_inventory_update)}${data.last_source ? ` · ${data.last_source}` : ""}`
                : "No inventory uploaded yet."}
            </span>
            <Link to={data.assets_total > 0 ? "/?tab=assets" : "/inventory/upload"}>
              {data.assets_total > 0 ? "View assets →" : "Upload CSV →"}
            </Link>
          </div>
        </>
      )}
      <SourceBadge datasetKey="assets_inventory" className="widget-source-badge" />
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div style={{ color, fontSize: 24, fontWeight: 700, lineHeight: 1.1 }}>
        {value.toLocaleString()}
      </div>
      <div style={{ fontSize: 12, color: "var(--text-muted, #64748b)" }}>{label}</div>
    </div>
  );
}
