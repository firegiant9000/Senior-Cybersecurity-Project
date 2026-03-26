import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { sendEmailVerification, sendPasswordResetEmail } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import "./SettingsPage.css";

interface UserProfile {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  auth_provider: string;
  created_at: string;
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
        if (!resp.ok) throw new Error("Failed to load profile");
        const data: UserProfile = await resp.json();
        if (!cancelled) setProfile(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load profile");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadProfile();
    return () => { cancelled = true; };
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const handleResendVerification = async () => {
    setActionMsg("");
    try {
      if (auth.currentUser) {
        await sendEmailVerification(auth.currentUser);
        setActionMsg("Verification email sent! Check your inbox.");
      }
    } catch {
      setActionMsg("Failed to send verification email. Try again later.");
    }
  };

  const handlePasswordReset = async () => {
    setActionMsg("");
    try {
      if (user?.email) {
        await sendPasswordResetEmail(auth, user.email);
        setActionMsg("Password reset email sent! Check your inbox.");
      }
    } catch {
      setActionMsg("Failed to send password reset email. Try again later.");
    }
  };

  return (
    <div className="settings-page">
      <div className="settings-card">
        <div className="settings-header">
          <h1>Account Settings</h1>
          <button className="back-btn" onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
        </div>

        {loading && <p className="settings-loading">Loading profile...</p>}
        {error && <div className="settings-error">{error}</div>}

        {!loading && !error && profile && (
          <div className="settings-sections">
            <section className="settings-section">
              <h2>Profile</h2>
              <div className="settings-field">
                <label>Email</label>
                <span>{profile.email}</span>
              </div>
              <div className="settings-field">
                <label>Role</label>
                <span className="role-badge">{profile.role}</span>
              </div>
              <div className="settings-field">
                <label>Auth Provider</label>
                <span>{profile.auth_provider}</span>
              </div>
              <div className="settings-field">
                <label>Account Created</label>
                <span>{new Date(profile.created_at).toLocaleDateString()}</span>
              </div>
              <div className="settings-field">
                <label>Status</label>
                <span className={`status-badge ${profile.is_active ? "active" : "inactive"}`}>
                  {profile.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </section>

            <section className="settings-section">
              <h2>Firebase Account</h2>
              <div className="settings-field">
                <label>Firebase UID</label>
                <span className="uid-text">{user?.uid}</span>
              </div>
              <div className="settings-field">
                <label>Email Verified</label>
                <span className={`status-badge ${user?.emailVerified ? "active" : "inactive"}`}>
                  {user?.emailVerified ? "Yes" : "No"}
                </span>
              </div>
              <div className="settings-field">
                <label>Last Sign-In</label>
                <span>{user?.metadata.lastSignInTime ?? "Unknown"}</span>
              </div>
            </section>

            <section className="settings-section">
              <h2>Actions</h2>
              {actionMsg && <div className="settings-action-msg">{actionMsg}</div>}
              <div className="settings-actions">
                {!user?.emailVerified && (
                  <button className="action-btn" onClick={handleResendVerification}>
                    Resend Verification Email
                  </button>
                )}
                <button className="action-btn" onClick={handlePasswordReset}>
                  Reset Password
                </button>
                <button className="logout-btn" onClick={handleLogout}>
                  Log Out
                </button>
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
