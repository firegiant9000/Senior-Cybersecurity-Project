/**
 * API client for read-only host scanner agent enrollments (Month 4 Phase 2).
 *
 * Org is derived from the caller's session server-side, so these endpoints are
 * not org-scoped in the path. The raw token is returned only once, by
 * enroll/rotate — it can never be fetched again.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export type AgentStatus =
  | "active"
  | "grace"
  | "stale"
  | "revoked"
  | "expired";

export interface Agent {
  id: number;
  org_id: number;
  name: string;
  token_prefix: string;
  scopes: string[] | null;
  created_by_user_id: number | null;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  expires_at: string | null;
  status: AgentStatus;
}

export interface AgentListResponse {
  total: number;
  items: Agent[];
}

export interface AgentTokenIssued {
  agent: Agent;
  /** Full bearer token; shown once and unrecoverable. */
  raw_token: string;
}

async function detailOrThrow(resp: Response, fallback: string): Promise<never> {
  const body = await resp.json().catch(() => ({}));
  throw new Error((body as { detail?: string }).detail ?? fallback);
}

export async function listAgents(): Promise<AgentListResponse> {
  const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/agents`);
  if (!resp.ok) await detailOrThrow(resp, "Failed to list agents");
  return resp.json();
}

export async function enrollAgent(
  name: string,
  scopes?: string[],
): Promise<AgentTokenIssued> {
  const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/agents/enroll`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, scopes: scopes ?? null }),
  });
  if (!resp.ok) await detailOrThrow(resp, "Failed to enroll agent");
  return resp.json();
}

export async function rotateAgent(
  agentId: number,
): Promise<AgentTokenIssued> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/agents/${agentId}/rotate`,
    { method: "POST" },
  );
  if (!resp.ok) await detailOrThrow(resp, "Failed to rotate agent");
  return resp.json();
}

export async function revokeAgent(agentId: number): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/agents/${agentId}`,
    { method: "DELETE" },
  );
  if (!resp.ok) await detailOrThrow(resp, "Failed to revoke agent");
}
