import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { sendEmailVerification, sendPasswordResetEmail } from "firebase/auth";
import { auth } from "../../firebase";
import { useAuth } from "../../context/AuthContext";
import type { UserProfile } from "../../api/account";

export default function AccountSection({ profile }: { profile: UserProfile }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [actionMsg, setActionMsg] = useState("");

  const handleLogout = async () => {
    await logout();
    navigate("/");
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
    <>
      <section className="settings-section">
        <h2>Your account</h2>
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
          <span
            className={`status-badge ${profile.is_active ? "active" : "inactive"}`}
          >
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
          <span
            className={`status-badge ${user?.emailVerified ? "active" : "inactive"}`}
          >
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
    </>
  );
}
