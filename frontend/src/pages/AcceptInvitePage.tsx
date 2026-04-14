import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
  getInviteByToken,
  acceptInvite,
  type InviteTokenInfo,
} from "../api/members";
import "../Dashboard.css";
import "./SettingsPage.css";

export default function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { refreshProfile } = useAuth();

  const [invite, setInvite] = useState<InviteTokenInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accepting, setAccepting] = useState(false);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("No invite token provided");
      setLoading(false);
      return;
    }
    getInviteByToken(token)
      .then((data) => setInvite(data))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Invite not found"),
      )
      .finally(() => setLoading(false));
  }, [token]);

  const handleAccept = async () => {
    if (!token) return;
    setAccepting(true);
    setError("");
    try {
      await acceptInvite(token);
      setAccepted(true);
      await refreshProfile();
      setTimeout(() => navigate("/"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept invite");
    } finally {
      setAccepting(false);
    }
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Organization Invite</h1>
      </header>

      <div className="settings-page settings-page--embedded">
        <div
          className="settings-card settings-card--wide"
          style={{ maxWidth: 520 }}
        >
          {loading && <p className="settings-loading">Loading invite...</p>}
          {error && <div className="settings-error">{error}</div>}

          {!loading && !error && invite && !accepted && (
            <div className="settings-sections">
              <section className="settings-section">
                <h2>You&apos;ve been invited</h2>
                <div className="settings-field">
                  <label>Organization</label>
                  <span>{invite.org_name}</span>
                </div>
                <div className="settings-field">
                  <label>Role</label>
                  <span className="role-badge">{invite.org_role}</span>
                </div>
                <div className="settings-field">
                  <label>Invited email</label>
                  <span>{invite.invited_email}</span>
                </div>
                <div className="settings-field">
                  <label>Expires</label>
                  <span>
                    {new Date(invite.expires_at).toLocaleDateString()}
                  </span>
                </div>
                <div
                  className="settings-actions"
                  style={{ marginTop: "1.5rem" }}
                >
                  <button
                    className="action-btn"
                    onClick={handleAccept}
                    disabled={accepting}
                  >
                    {accepting ? "Joining..." : "Accept & Join"}
                  </button>
                  <button className="action-btn" onClick={() => navigate("/")}>
                    Decline
                  </button>
                </div>
              </section>
            </div>
          )}

          {accepted && (
            <div
              className="settings-action-msg"
              style={{ textAlign: "center", padding: "2rem" }}
            >
              You have joined the organization! Redirecting...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
