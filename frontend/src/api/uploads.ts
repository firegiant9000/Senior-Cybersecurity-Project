/**
 * API client for organization file uploads.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export interface OrgUpload {
  id: number;
  org_id: number;
  uploaded_by: number | null;
  original_filename: string;
  stored_filename: string;
  file_size_bytes: number;
  content_type: string;
  upload_purpose: string | null;
  created_at: string;
}

export interface OrgUploadListResponse {
  total: number;
  page: number;
  page_size: number;
  items: OrgUpload[];
}

export async function listUploads(
  orgId: number,
  page = 1,
  pageSize = 20,
): Promise<OrgUploadListResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/uploads?page=${page}&page_size=${pageSize}`,
  );
  if (!resp.ok) throw new Error("Failed to load uploads");
  return resp.json();
}

export async function uploadFile(
  orgId: number,
  file: File,
  purpose?: string,
): Promise<OrgUpload> {
  const formData = new FormData();
  formData.append("file", file);
  const url = purpose
    ? `${API_BASE_URL}/api/v1/organizations/${orgId}/uploads?purpose=${encodeURIComponent(purpose)}`
    : `${API_BASE_URL}/api/v1/organizations/${orgId}/uploads`;
  const resp = await fetchWithAuth(url, { method: "POST", body: formData });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to upload file",
    );
  }
  return resp.json();
}

export async function deleteUpload(
  orgId: number,
  uploadId: number,
): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/uploads/${uploadId}`,
    { method: "DELETE" },
  );
  if (!resp.ok) throw new Error("Failed to delete upload");
}

export async function downloadUpload(
  orgId: number,
  uploadId: number,
  filename: string,
): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/uploads/${uploadId}/download`,
  );
  if (!resp.ok) throw new Error("Failed to download file");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
