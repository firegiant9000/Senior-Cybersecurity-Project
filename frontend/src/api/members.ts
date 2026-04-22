/**
 * API client for organization members and invites.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

// ── Invite types ─────────────────────────────────────────────────────────────

export interface OrgInvite {
  id: number;
  org_id: number;
  email: string;
  role: string;
  status: string;
  inviter_id: number | null;
  expires_at: string;
  created_at: string;
}

export interface InviteListResponse {
  total: number;
  page: number;
  page_size: number;
  items: OrgInvite[];
}

export interface InviteTokenInfo {
  invite_token: string;
  org_name: string;
  org_role: string;
  invited_email: string;
  expires_at: string;
}

// ── Member types ─────────────────────────────────────────────────────────────

export interface OrgMember {
  user_id: number;
  email: string;
  role: string | null;
  is_active: boolean;
  created_at: string;
}

export interface MemberListResponse {
  total: number;
  page: number;
  page_size: number;
  items: OrgMember[];
}

// ── Invite API ───────────────────────────────────────────────────────────────

export async function createInvite(
  orgId: number,
  email: string,
  orgRole: string = "member",
): Promise<OrgInvite> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/invites`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, org_role: orgRole }),
    },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to create invite",
    );
  }
  return resp.json();
}

export async function listInvites(
  orgId: number,
  page = 1,
  pageSize = 20,
): Promise<InviteListResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/invites?page=${page}&page_size=${pageSize}`,
  );
  if (!resp.ok) throw new Error("Failed to list invites");
  return resp.json();
}

export async function revokeInvite(
  orgId: number,
  inviteId: number,
): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/invites/${inviteId}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw new Error("Failed to revoke invite");
}

export async function getInviteByToken(
  token: string,
): Promise<InviteTokenInfo> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/invites/${encodeURIComponent(token)}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Invite not found");
  }
  return resp.json();
}

export async function acceptInvite(
  token: string,
): Promise<{ detail: string; org_id: number }> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/invites/${encodeURIComponent(token)}/accept`,
    { method: "POST" },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to accept invite",
    );
  }
  return resp.json();
}

// ── Member API ───────────────────────────────────────────────────────────────

export async function listMembers(
  orgId: number,
  page = 1,
  pageSize = 20,
): Promise<MemberListResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/members?page=${page}&page_size=${pageSize}`,
  );
  if (!resp.ok) throw new Error("Failed to list members");
  return resp.json();
}

export async function updateMemberRole(
  orgId: number,
  userId: number,
  orgRole: string,
): Promise<OrgMember> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/members/${userId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: orgRole }),
    },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to update role",
    );
  }
  return resp.json();
}

export async function removeMember(
  orgId: number,
  userId: number,
): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/members/${userId}`,
    { method: "DELETE" },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to remove member",
    );
  }
}
