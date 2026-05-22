/**
 * Integrations API client — Month 2 Phase E (M365 / Entra OAuth spike).
 *
 * The status endpoint always responds (even when the integration is disabled)
 * with `{ enabled: false, connection: { connected: false } }`, so the
 * IntegrationsPage can render a single "feature disabled" state without
 * special-casing 404/503.
 */

import {
  API_BASE_URL,
  fetchWithAuth,
  getJsonAuth,
} from "./fetchWithAuth";

export interface M365Connection {
  connected: boolean;
  status?: string;
  tenant_id?: string | null;
  account_label?: string | null;
  scopes?: string | null;
  last_sync_at?: string | null;
  last_sync_status?: string | null;
  device_count?: number | null;
}

export interface M365StatusResponse {
  enabled: boolean;
  connection: M365Connection;
}

export interface M365ConsentResponse {
  authorize_url: string;
  state: string;
  expires_at: string;
}

export interface M365SyncResponse {
  status: "succeeded" | "failed" | "partial";
  device_count: number;
  synced_at: string;
}

export async function fetchM365Status(
  orgId: number,
  signal: AbortSignal,
): Promise<M365StatusResponse> {
  return getJsonAuth<M365StatusResponse>(
    `${API_BASE_URL}/api/v1/integrations/m365?org_id=${orgId}`,
    signal,
  );
}

async function postJsonAuth<T>(url: string): Promise<T> {
  const response = await fetchWithAuth(url, { method: "POST" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Request failed: ${response.statusText}`,
    );
  }
  return response.json() as Promise<T>;
}

export async function startM365Consent(orgId: number): Promise<M365ConsentResponse> {
  return postJsonAuth<M365ConsentResponse>(
    `${API_BASE_URL}/api/v1/integrations/m365/consent?org_id=${orgId}`,
  );
}

export async function syncM365(orgId: number): Promise<M365SyncResponse> {
  return postJsonAuth<M365SyncResponse>(
    `${API_BASE_URL}/api/v1/integrations/m365/sync?org_id=${orgId}`,
  );
}

export async function disconnectM365(orgId: number): Promise<void> {
  const response = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/integrations/m365?org_id=${orgId}`,
    { method: "DELETE" },
  );
  if (!response.ok && response.status !== 204) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Request failed: ${response.statusText}`,
    );
  }
}
