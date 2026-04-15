/**
 * API client for organization domain management.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export interface OrgDomain {
  id: number;
  org_id: number;
  domain_name: string;
  is_verified: boolean;
  added_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface OrgDomainListResponse {
  total: number;
  page: number;
  page_size: number;
  items: OrgDomain[];
}

export async function listDomains(
  orgId: number,
  page = 1,
  pageSize = 20,
): Promise<OrgDomainListResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/domains?page=${page}&page_size=${pageSize}`,
  );
  if (!resp.ok) throw new Error("Failed to load domains");
  return resp.json();
}

export async function addDomain(
  orgId: number,
  domainName: string,
): Promise<OrgDomain> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/domains`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain_name: domainName }),
    },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const detail = (body as { detail?: string | { msg: string }[] }).detail;
    const message =
      Array.isArray(detail)
        ? detail.map((d) => d.msg).join("; ")
        : detail ?? "Failed to add domain";
    throw new Error(message);
  }
  return resp.json();
}

export async function deleteDomain(
  orgId: number,
  domainId: number,
): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/domains/${domainId}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw new Error("Failed to delete domain");
}
