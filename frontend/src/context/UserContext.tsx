import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";

/** Mirrors `OrganizationRead` from the API. */
export interface OrganizationProfile {
  id: number;
  name: string;
  logo_url?: string | null;
  primary_domain?: string | null;
  industry_label: string;
  ic3_sector: string;
  primary_state: string;
  employee_range: string;
  revenue_range: string | null;
}

interface UserContextType {
  organization: OrganizationProfile | null;
  loading: boolean;
  error: boolean;
  refreshOrganization: () => Promise<void>;
}

const UserContext = createContext<UserContextType | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const { user, orgId } = useAuth();
  const [organization, setOrganization] = useState<OrganizationProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    if (!user || orgId == null) {
      setOrganization(null);
      setError(false);
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/organizations/${orgId}`);
      if (!resp.ok) {
        setError(true);
        setOrganization(null);
        return;
      }
      const data = (await resp.json()) as OrganizationProfile;
      setOrganization(data);
    } catch {
      setError(true);
      setOrganization(null);
    } finally {
      setLoading(false);
    }
  }, [user, orgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const refreshOrganization = useCallback(async () => {
    await load();
  }, [load]);

  return (
    <UserContext.Provider
      value={{ organization, loading, error, refreshOrganization }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUserContext(): UserContextType {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUserContext must be used within UserProvider");
  return ctx;
}
