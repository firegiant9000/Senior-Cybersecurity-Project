/**
 * API client for vendor (technology stack) management.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export interface OrgVendor {
  id: number;
  org_id: number;
  vendor_name: string;
  product_name: string;
  created_at: string;
  updated_at: string;
  matched_kev_count: number;
}

export interface OrgVendorListResponse {
  total: number;
  page: number;
  page_size: number;
  items: OrgVendor[];
}

export interface OrgVendorImportResponse {
  imported: number;
  skipped: number;
  errors: string[];
}

export async function listVendors(
  orgId: number,
  page = 1,
  pageSize = 50,
): Promise<OrgVendorListResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/vendors?page=${page}&page_size=${pageSize}`,
  );
  if (!resp.ok) throw new Error("Failed to load vendors");
  return resp.json();
}

export async function createVendor(
  orgId: number,
  vendorName: string,
  productName: string,
): Promise<OrgVendor> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/vendors`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vendor_name: vendorName, product_name: productName }),
    },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Failed to add vendor");
  }
  return resp.json();
}

export async function updateVendor(
  orgId: number,
  vendorId: number,
  vendorName: string,
  productName: string,
): Promise<OrgVendor> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/vendors/${vendorId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vendor_name: vendorName, product_name: productName }),
    },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Failed to update vendor");
  }
  return resp.json();
}

export async function deleteVendor(orgId: number, vendorId: number): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/vendors/${vendorId}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw new Error("Failed to delete vendor");
}

export async function importVendorsCsv(
  orgId: number,
  file: File,
): Promise<OrgVendorImportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/vendors/import`,
    { method: "POST", body: formData },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Failed to import CSV");
  }
  return resp.json();
}

export async function autocompleteVendors(
  query: string,
  field: "vendor" | "product" = "vendor",
  vendor?: string,
): Promise<string[]> {
  const params = new URLSearchParams({ q: query, field });
  if (vendor) params.set("vendor", vendor);
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/vendors/autocomplete?${params}`,
  );
  if (!resp.ok) return [];
  return resp.json();
}
