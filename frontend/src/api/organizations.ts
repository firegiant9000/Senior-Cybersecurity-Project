/**
 * API client for organisation profile updates.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export type OrganizationUpdateBody = Partial<{
  name: string;
  logo_url: string | null;
  primary_domain: string | null;
  industry_label: string | null;
  primary_state: string | null;
  employee_range: string | null;
  revenue_range: string | null;
  security_controls: Record<string, string> | null;
  cloud_providers: string[] | null;
  compliance_frameworks: string[] | null;
  data_types: string[] | null;
  device_count_range: string | null;
  incident_history: string | null;
}>;

export async function updateOrganization(
  orgId: number,
  body: OrganizationUpdateBody,
): Promise<void> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || "Failed to save organisation");
  }
}
