/**
 * Integrations page — Month 2 Phase E (M365 / Entra OAuth spike).
 *
 * Renders a single Microsoft 365 card with connect / sync / disconnect
 * actions. Hidden behind ENABLE_M365_INTEGRATION; when the backend reports
 * `enabled: false` the page shows a "feature disabled" notice instead.
 */

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.tsx";
import {
  M365StatusResponse,
  M365SyncResponse,
  disconnectM365,
  fetchM365Status,
  startM365Consent,
  syncM365,
} from "../api/integrations.ts";

type Banner =
  | { kind: "success"; text: string }
  | { kind: "error"; text: string }
  | null;

export default function IntegrationsPage() {
  const { orgId } = useAuth();
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState<M365StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<Banner>(null);
  const [lastSync, setLastSync] = useState<M365SyncResponse | null>(null);

  const refresh = useCallback(async () => {
    if (orgId == null) return;
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    try {
      const data = await fetchM365Status(orgId, controller.signal);
      setStatus(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
    return () => controller.abort();
  }, [orgId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Surface OAuth callback outcomes via the ?m365= query string.
  useEffect(() => {
    const result = params.get("m365");
    if (!result) return;
    const message = params.get("message") ?? "";
    if (result === "connected") {
      setBanner({
        kind: "success",
        text: message
          ? `Connected to Microsoft 365 (${message}).`
          : "Connected to Microsoft 365.",
      });
    } else if (result === "error") {
      setBanner({
        kind: "error",
        text: `Microsoft 365 connection failed: ${message || "unknown error"}`,
      });
    }
    params.delete("m365");
    params.delete("message");
    setParams(params, { replace: true });
  }, [params, setParams]);

  const handleConnect = async () => {
    if (orgId == null) return;
    setBusy(true);
    setError(null);
    try {
      const { authorize_url } = await startM365Consent(orgId);
      window.location.assign(authorize_url);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  const handleSync = async () => {
    if (orgId == null) return;
    setBusy(true);
    setError(null);
    try {
      const result = await syncM365(orgId);
      setLastSync(result);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleDisconnect = async () => {
    if (orgId == null) return;
    if (!window.confirm("Disconnect Microsoft 365 for this organization?")) return;
    setBusy(true);
    setError(null);
    try {
      await disconnectM365(orgId);
      setLastSync(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (orgId == null) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1>Integrations</h1>
        <p>Create or join an organization before connecting integrations.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1>Integrations</h1>
        <p>Loading…</p>
      </div>
    );
  }

  if (!status?.enabled) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1>Integrations</h1>
        <p>
          The Microsoft 365 integration is not enabled in this environment.
          Set <code>ENABLE_M365_INTEGRATION=true</code> in the backend to try
          it locally.
        </p>
      </div>
    );
  }

  const conn = status.connection;
  return (
    <div style={{ padding: "2rem", maxWidth: 720 }}>
      <h1>Integrations</h1>
      <p>
        Connect cloud sources to populate your asset inventory automatically.
        Microsoft 365 is currently the only supported source (preview).
      </p>

      {banner && (
        <div
          role="status"
          data-testid="m365-banner"
          style={{
            margin: "1rem 0",
            padding: "0.75rem 1rem",
            borderRadius: 6,
            background: banner.kind === "success" ? "#e6f7ec" : "#fdecea",
            color: banner.kind === "success" ? "#1b5e20" : "#b71c1c",
          }}
        >
          {banner.text}
        </div>
      )}

      <section
        data-testid="m365-card"
        style={{
          border: "1px solid #d0d7de",
          borderRadius: 8,
          padding: "1.25rem",
          marginTop: "1rem",
        }}
      >
        <header style={{ display: "flex", justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Microsoft 365 / Entra</h2>
          <span data-testid="m365-status">
            {conn.connected ? conn.status ?? "connected" : "not connected"}
          </span>
        </header>

        {conn.connected ? (
          <dl style={{ marginTop: "1rem" }}>
            {conn.account_label && (
              <>
                <dt>Account</dt>
                <dd>{conn.account_label}</dd>
              </>
            )}
            {conn.tenant_id && (
              <>
                <dt>Tenant ID</dt>
                <dd>
                  <code>{conn.tenant_id}</code>
                </dd>
              </>
            )}
            <dt>Last sync</dt>
            <dd>
              {conn.last_sync_at
                ? `${new Date(conn.last_sync_at).toLocaleString()} — ${
                    conn.last_sync_status ?? "unknown"
                  }${
                    conn.device_count != null
                      ? ` (${conn.device_count} devices)`
                      : ""
                  }`
                : "Never"}
            </dd>
          </dl>
        ) : (
          <p style={{ marginTop: "1rem" }}>
            Sign in with a Microsoft 365 admin to pull your managed devices.
            Requires Intune to see device data.
          </p>
        )}

        {error && (
          <p role="alert" style={{ color: "#b71c1c" }}>
            {error}
          </p>
        )}

        <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
          {!conn.connected && (
            <button onClick={handleConnect} disabled={busy} data-testid="m365-connect">
              {busy ? "Redirecting…" : "Connect Microsoft 365"}
            </button>
          )}
          {conn.connected && (
            <>
              <button onClick={handleSync} disabled={busy} data-testid="m365-sync">
                {busy ? "Syncing…" : "Sync devices now"}
              </button>
              <button
                onClick={handleDisconnect}
                disabled={busy}
                data-testid="m365-disconnect"
              >
                Disconnect
              </button>
            </>
          )}
        </div>

        {lastSync && (
          <p data-testid="m365-sync-result" style={{ marginTop: "1rem" }}>
            Last sync attempt: {lastSync.status} — {lastSync.device_count} devices at{" "}
            {new Date(lastSync.synced_at).toLocaleString()}.
          </p>
        )}
      </section>
    </div>
  );
}
