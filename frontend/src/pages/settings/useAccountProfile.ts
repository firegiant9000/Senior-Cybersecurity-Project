import { useState, useEffect } from "react";
import { fetchMe, UserProfile } from "../../api/account";

export function useAccountProfile(): {
  profile: UserProfile | null;
  loading: boolean;
  error: string;
} {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const data = await fetchMe();
        if (!cancelled) setProfile(data);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Failed to load profile",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadProfile();
    return () => {
      cancelled = true;
    };
  }, []);

  return { profile, loading, error };
}
