import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export interface UserProfile {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  auth_provider: string;
  created_at: string;
  org_id: number | null;
  org_role: string | null;
}

export async function fetchMe(): Promise<UserProfile> {
  const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
  if (!resp.ok) throw new Error("Failed to load profile");
  return (await resp.json()) as UserProfile;
}
