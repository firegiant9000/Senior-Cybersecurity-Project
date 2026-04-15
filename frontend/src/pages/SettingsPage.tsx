import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { sendEmailVerification, sendPasswordResetEmail } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import {
  OrgMember,
  OrgInvite,
  listMembers,
  listInvites,
  createInvite,
  revokeInvite,
  updateMemberRole,
  removeMember,
} from "../api/members";
import "../Dashboard.css";
import "./SettingsPage.css";

interface UserProfile {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  auth_provider: string;
  created_at: string;
  org_id: number | null;
  org_role: string | null;
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  // Members & invites state
  const [membersList, setMembersList] = useState<OrgMember[]>([]);
  const [membersTotal, setMembersTotal] = useState(0);
  const [membersPage, setMembersPage] = useState(1);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState("");
  const [membersMsg, setMembersMsg] = useState("");
  const [invitesList, setInvitesList] = useState<OrgInvite[]>([]);
  const [invitesTotal, setInvitesTotal] = useState(0);
  const [invitesPage, setInvitesPage] = useState(1);
  const [invitesLoading, setInvitesLoading] = useState(false);
  const [invitesError, setInvitesError] = useState("");
  const [invitesMsg, setInvitesMsg] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const membersPageSize = 20;

  const loadMembers = useCallback(async (orgId: number, page: number) => {
    setMembersLoading(true);
    setMembersError("");
    try {
      const data = await listMembers(orgId, page, membersPageSize);
      setMembersList(data.items);
      setMembersTotal(data.total);
    } catch {
      setMembersError("Failed to load members");
    } finally {
      setMembersLoading(false);
    }
  }, []);

  const loadInvites = useCallback(async (orgId: number, page: number) => {
    setInvitesLoading(true);
    setInvitesError("");
    try {
      const data = await listInvites(orgId, page, membersPageSize);
      setInvitesList(data.items);
      setInvitesTotal(data.total);
    } catch {
      setInvitesError("Failed to load invites");
    } finally {
      setInvitesLoading(false);
    }
  }, []);

  const canManageMembers =
    profile != null &&
    (profile.role === "admin" ||
      profile.org_role === "admin" ||
      profile.org_role === "owner");

  useEffect(() => {
    if (profile?.org_id && canManageMembers) {
      loadMembers(profile.org_id, membersPage);
    }
  }, [profile?.org_id, membersPage, loadMembers, canManageMembers]);

  useEffect(() => {
    if (profile?.org_id && canManageMembers) {
      loadInvites(profile.org_id, invitesPage);
    }
  }, [profile?.org_id, invitesPage, loadInvites, canManageMembers]);

  const handleSendInvite = async () => {
    if (!profile?.org_id || !inviteEmail.trim()) return;
    setInvitesError("");
    setInvitesMsg("");
    try {
      await createInvite(profile.org_id, inviteEmail.trim(), inviteRole);
      setInviteEmail("");
      setInviteRole("member");
      setInvitesMsg("Invite sent");
      loadInvites(profile.org_id, 1);
      setInvitesPage(1);
    } catch (err) {
      setInvitesError(
        err instanceof Error ? err.message : "Failed to send invite",
      );
    }
  };

  const handleRevokeInvite = async (inviteId: number) => {
    if (!profile?.org_id) return;
    setInvitesError("");
    try {
      await revokeInvite(profile.org_id, inviteId);
      loadInvites(profile.org_id, invitesPage);
    } catch {
      setInvitesError("Failed to revoke invite");
    }
  };

  const handleUpdateMemberRole = async (userId: number, newRole: string) => {
    if (!profile?.org_id) return;
    setMembersError("");
    try {
      await updateMemberRole(profile.org_id, userId, newRole);
      setMembersMsg("Role updated");
      loadMembers(profile.org_id, membersPage);
    } catch (err) {
      setMembersError(
        err instanceof Error ? err.message : "Failed to update role",
      );
    }
  };

  const handleRemoveMember = async (userId: number) => {
    if (!profile?.org_id) return;
    setMembersError("");
    try {
      await removeMember(profile.org_id, userId);
      setMembersMsg("Member removed");
      loadMembers(profile.org_id, membersPage);
    } catch (err) {
      setMembersError(
        err instanceof Error ? err.message : "Failed to remove member",
      );
    }
  };

  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
        if (!resp.ok) throw new Error("Failed to load profile");
        const data: UserProfile = await resp.json();
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
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Settings</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
          {profile?.org_id != null && (
            <button type="button" onClick={() => navigate("/org-profile")}>
              Organization Profile
            </button>
          )}
        </div>
      </header>

      <div className="settings-page settings-page--embedded">
        <div className="settings-card settings-card--wide">
          {loading && <p className="settings-loading">Loading profile...</p>}
          {error && <div className="settings-error">{error}</div>}

          {!loading && !error && profile && (
            <div className="settings-sections">
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
                  <span>
                    {new Date(profile.created_at).toLocaleDateString()}
                  </span>
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
                {actionMsg && (
                  <div className="settings-action-msg">{actionMsg}</div>
                )}
                <div className="settings-actions">
                  {!user?.emailVerified && (
                    <button
                      className="action-btn"
                      onClick={handleResendVerification}
                    >
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

              {profile.org_id != null && canManageMembers && (
                <section className="settings-section">
                  <h2>Members</h2>
                  <p className="tech-stack-description">
                    Manage who belongs to your organization and their roles.
                  </p>

                  {membersMsg && (
                    <div className="settings-action-msg">{membersMsg}</div>
                  )}
                  {membersError && (
                    <div
                      className="settings-error"
                      style={{
                        whiteSpace: "pre-line",
                        marginBottom: "0.75rem",
                      }}
                    >
                      {membersError}
                    </div>
                  )}

                  {membersLoading ? (
                    <p className="settings-loading">Loading members...</p>
                  ) : membersList.length === 0 ? (
                    <p className="vendor-empty">No members found.</p>
                  ) : (
                    <>
                      <table className="vendor-table">
                        <thead>
                          <tr>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Joined</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {membersList.map((m) => (
                            <tr key={m.id}>
                              <td>{m.email}</td>
                              <td>
                                {m.org_role === "owner" ? (
                                  <span className="role-badge">
                                    {m.org_role}
                                  </span>
                                ) : (
                                  <select
                                    className="member-role-select"
                                    value={m.org_role ?? "member"}
                                    onChange={(e) =>
                                      handleUpdateMemberRole(
                                        m.id,
                                        e.target.value,
                                      )
                                    }
                                    disabled={
                                      m.id === profile.id ||
                                      profile.org_role !== "owner" && profile.role !== "admin"
                                    }
                                  >
                                    <option value="member">member</option>
                                    <option value="admin">admin</option>
                                  </select>
                                )}
                              </td>
                              <td>
                                {new Date(m.created_at).toLocaleDateString()}
                              </td>
                              <td>
                                {m.org_role !== "owner" &&
                                  m.id !== profile.id && (
                                    <button
                                      className="vendor-delete-btn"
                                      onClick={() => handleRemoveMember(m.id)}
                                      title="Remove member"
                                    >
                                      &times;
                                    </button>
                                  )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {membersTotal > membersPageSize && (
                        <div className="vendor-pagination">
                          <button
                            className="action-btn"
                            disabled={membersPage <= 1}
                            onClick={() => setMembersPage((p) => p - 1)}
                          >
                            Previous
                          </button>
                          <span className="vendor-page-info">
                            Page {membersPage} of{" "}
                            {Math.ceil(membersTotal / membersPageSize)}
                          </span>
                          <button
                            className="action-btn"
                            disabled={
                              membersPage >=
                              Math.ceil(membersTotal / membersPageSize)
                            }
                            onClick={() => setMembersPage((p) => p + 1)}
                          >
                            Next
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </section>
              )}

              {profile.org_id != null && canManageMembers && (
                <section className="settings-section">
                  <h2>Invitations</h2>
                  <p className="tech-stack-description">
                    Invite users to join your organization. They will need to
                    create an account with the invited email and accept the
                    invite.
                  </p>

                  {invitesMsg && (
                    <div className="settings-action-msg">{invitesMsg}</div>
                  )}
                  {invitesError && (
                    <div
                      className="settings-error"
                      style={{
                        whiteSpace: "pre-line",
                        marginBottom: "0.75rem",
                      }}
                    >
                      {invitesError}
                    </div>
                  )}

                  <div className="vendor-add-form">
                    <div className="vendor-input-wrapper">
                      <input
                        type="email"
                        placeholder="user@example.com"
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                        onKeyDown={(e) =>
                          e.key === "Enter" && handleSendInvite()
                        }
                      />
                    </div>
                    <select
                      className="member-role-select"
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                    >
                      <option value="member">member</option>
                      <option value="admin">admin</option>
                    </select>
                    <button
                      className="action-btn"
                      onClick={handleSendInvite}
                      disabled={!inviteEmail.trim()}
                    >
                      Send Invite
                    </button>
                  </div>

                  {invitesLoading ? (
                    <p className="settings-loading">Loading invites...</p>
                  ) : invitesList.length === 0 ? (
                    <p className="vendor-empty">No pending invitations.</p>
                  ) : (
                    <>
                      <table className="vendor-table">
                        <thead>
                          <tr>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Status</th>
                            <th>Expires</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {invitesList.map((inv) => (
                            <tr key={inv.id}>
                              <td>{inv.invited_email}</td>
                              <td>{inv.org_role}</td>
                              <td>
                                <span
                                  className={`status-badge ${inv.status === "pending" ? "active" : "inactive"}`}
                                >
                                  {inv.status}
                                </span>
                              </td>
                              <td>
                                {new Date(inv.expires_at).toLocaleDateString()}
                              </td>
                              <td>
                                {inv.status === "pending" && (
                                  <button
                                    className="vendor-delete-btn"
                                    onClick={() => handleRevokeInvite(inv.id)}
                                    title="Revoke invite"
                                  >
                                    &times;
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {invitesTotal > membersPageSize && (
                        <div className="vendor-pagination">
                          <button
                            className="action-btn"
                            disabled={invitesPage <= 1}
                            onClick={() => setInvitesPage((p) => p - 1)}
                          >
                            Previous
                          </button>
                          <span className="vendor-page-info">
                            Page {invitesPage} of{" "}
                            {Math.ceil(invitesTotal / membersPageSize)}
                          </span>
                          <button
                            className="action-btn"
                            disabled={
                              invitesPage >=
                              Math.ceil(invitesTotal / membersPageSize)
                            }
                            onClick={() => setInvitesPage((p) => p + 1)}
                          >
                            Next
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
