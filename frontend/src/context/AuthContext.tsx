import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import {
  User,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import { auth } from "../firebase";
import { API_BASE_URL } from "../api/fetchWithAuth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  orgId: number | null;
  orgLoading: boolean;
  profileError: boolean;
  role: string | null;
  orgRole: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [orgId, setOrgId] = useState<number | null>(null);
  const [orgLoading, setOrgLoading] = useState(true);
  const [role, setRole] = useState<string | null>(null);
  const [orgRole, setOrgRole] = useState<string | null>(null);

  const [profileError, setProfileError] = useState(false);

  const fetchProfile = useCallback(async (firebaseUser: User, maxRetries = 1) => {
    setProfileError(false);
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const token = await firebaseUser.getIdToken();
        const resp = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (resp.ok) {
          const data = await resp.json();
          setOrgId(data.org_id ?? null);
          setRole(data.role?.toLowerCase() ?? null);
          setOrgRole(data.org_role?.toLowerCase() ?? null);
          setOrgLoading(false);
          return;
        }
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, 1000));
          continue;
        }
        setProfileError(true);
      } catch {
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, 1000));
          continue;
        }
        setProfileError(true);
      }
    }
    setOrgLoading(false);
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
      if (firebaseUser) {
        setOrgLoading(true);
        fetchProfile(firebaseUser);
      } else {
        setOrgId(null);
        setRole(null);
        setOrgRole(null);
        setOrgLoading(false);
      }
    });
    return unsubscribe;
  }, [fetchProfile]);

  const login = async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password);
  };

  const signup = async (email: string, password: string) => {
    await createUserWithEmailAndPassword(auth, email, password);
  };

  const logout = async () => {
    await signOut(auth);
  };

  const getIdToken = async () => {
    if (!user) return null;
    return user.getIdToken();
  };

  const refreshProfile = useCallback(async () => {
    if (user) {
      setOrgLoading(true);
      await fetchProfile(user);
    }
  }, [user, fetchProfile]);

  return (
    <AuthContext.Provider value={{ user, loading, orgId, orgLoading, profileError, role, orgRole, login, signup, logout, getIdToken, refreshProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
