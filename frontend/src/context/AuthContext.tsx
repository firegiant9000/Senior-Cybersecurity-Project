import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import {
  User,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendEmailVerification,
  signOut,
} from "firebase/auth";
import { auth } from "../firebase";
import { API_BASE_URL } from "../api/fetchWithAuth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  orgId: number | null;
  orgIsDemo: boolean;
  orgLoading: boolean;
  profileError: boolean;
  /** The API refused the profile because the account's email is not verified yet. */
  emailUnverified: boolean;
  role: string | null;
  orgRole: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
  refreshProfile: () => Promise<void>;
  /** Sends a verification email; resolves to a message to show the user. */
  resendVerification: () => Promise<string>;
  /** Reloads the Firebase user, force-refreshes the token, then re-fetches the profile. */
  confirmVerification: () => Promise<boolean>;
}

const EMAIL_NOT_VERIFIED_DETAIL = "Email address not verified";

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [orgId, setOrgId] = useState<number | null>(null);
  const [orgIsDemo, setOrgIsDemo] = useState(false);
  const [orgLoading, setOrgLoading] = useState(true);
  const [role, setRole] = useState<string | null>(null);
  const [orgRole, setOrgRole] = useState<string | null>(null);

  const [profileError, setProfileError] = useState(false);
  const [emailUnverified, setEmailUnverified] = useState(false);

  const fetchProfile = useCallback(async (firebaseUser: User, maxRetries = 1) => {
    setProfileError(false);
    // A previous user's verify screen must not survive into this fetch's outcome.
    setEmailUnverified(false);
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        // Force-refresh on retry to avoid using a stale cached token.
        const token = await firebaseUser.getIdToken(attempt > 0);
        const resp = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (resp.ok) {
          const data = await resp.json();
          setOrgId(data.org_id ?? null);
          setOrgIsDemo(Boolean(data.org_is_demo));
          setRole(data.role?.toLowerCase() ?? null);
          setOrgRole(data.org_role?.toLowerCase() ?? null);
          setEmailUnverified(false);
          setOrgLoading(false);
          return true;
        }
        if (resp.status === 403) {
          const body = await resp.json().catch(() => ({}));
          if ((body as { detail?: string }).detail === EMAIL_NOT_VERIFIED_DETAIL) {
            // Not an outage: show the verify screen. Clear orgLoading or the
            // route guard stays on "Loading..." forever.
            setEmailUnverified(true);
            setOrgLoading(false);
            return false;
          }
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
    return false;
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
        setOrgIsDemo(false);
        setRole(null);
        setOrgRole(null);
        setEmailUnverified(false);
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

  const resendVerification = async () => {
    if (!user) return "Sign in to resend the verification email.";
    try {
      await sendEmailVerification(user);
      return "Verification email sent. Check your inbox.";
    } catch (err) {
      if ((err as { code?: string }).code === "auth/too-many-requests") {
        return "A verification email was sent recently. Check your inbox or try again in a few minutes.";
      }
      return "We couldn't send the verification email. Please try again later.";
    }
  };

  const confirmVerification = async () => {
    if (!user) return false;
    await user.reload();
    // Force a new token so it carries the updated email_verified claim.
    await user.getIdToken(true);
    // True only when the server accepted the profile load with the new token.
    return fetchProfile(user);
  };

  return (
    <AuthContext.Provider value={{ user, loading, orgId, orgIsDemo, orgLoading, profileError, emailUnverified, role, orgRole, login, signup, logout, getIdToken, refreshProfile, resendVerification, confirmVerification }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
