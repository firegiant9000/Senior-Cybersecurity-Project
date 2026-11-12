import { useState, useEffect, useCallback } from "react";
import {
  OrgMember,
  OrgInvite,
  listMembers,
  listInvites,
  createInvite,
  revokeInvite,
  updateMemberRole,
  removeMember,
} from "../../api/members";

const membersPageSize = 20;

export default function TeamSection({
  orgId,
  userId,
  role,
  orgRole,
}: {
  orgId: number;
  userId: number;
  role: string | null;
  orgRole: string | null;
}) {
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
  const [createdInviteLink, setCreatedInviteLink] = useState<string | null>(
    null,
  );
  const [inviteLinkCopied, setInviteLinkCopied] = useState(false);

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

  useEffect(() => {
    loadMembers(orgId, membersPage);
  }, [orgId, membersPage, loadMembers]);

  useEffect(() => {
    loadInvites(orgId, invitesPage);
  }, [orgId, invitesPage, loadInvites]);

  const handleCopyInviteLink = async () => {
    if (!createdInviteLink) return;
    try {
      await window.navigator.clipboard.writeText(createdInviteLink);
      setInviteLinkCopied(true);
    } catch {
      // Clipboard rejected or unavailable: the link stays visible to select.
      setInviteLinkCopied(false);
    }
  };

  const handleSendInvite = async () => {
    if (!orgId || !inviteEmail.trim()) return;
    setInvitesError("");
    setInvitesMsg("");
    setCreatedInviteLink(null);
    setInviteLinkCopied(false);
    try {
      const created = await createInvite(
        orgId,
        inviteEmail.trim(),
        inviteRole,
      );
      setInviteEmail("");
      setInviteRole("member");
      setCreatedInviteLink(
        `${window.location.origin}/invites/${encodeURIComponent(created.token)}`,
      );
      setInvitesMsg("Invite created. Copy the link and send it.");
      loadInvites(orgId, 1);
      setInvitesPage(1);
    } catch (err) {
      setInvitesError(
        err instanceof Error ? err.message : "Failed to send invite",
      );
    }
  };

  const handleRevokeInvite = async (inviteId: number) => {
    if (!orgId) return;
    setInvitesError("");
    try {
      await revokeInvite(orgId, inviteId);
      setCreatedInviteLink(null);
      setInviteLinkCopied(false);
      setInvitesMsg("");
      loadInvites(orgId, invitesPage);
    } catch {
      setInvitesError("Failed to revoke invite");
    }
  };

  const handleUpdateMemberRole = async (memberId: number, newRole: string) => {
    if (!orgId) return;
    setMembersError("");
    try {
      await updateMemberRole(orgId, memberId, newRole);
      setMembersMsg("Role updated");
      loadMembers(orgId, membersPage);
    } catch (err) {
      setMembersError(
        err instanceof Error ? err.message : "Failed to update role",
      );
    }
  };

  const handleRemoveMember = async (memberId: number) => {
    if (!orgId) return;
    setMembersError("");
    try {
      await removeMember(orgId, memberId);
      setMembersMsg("Member removed");
      loadMembers(orgId, membersPage);
    } catch (err) {
      setMembersError(
        err instanceof Error ? err.message : "Failed to remove member",
      );
    }
  };

  return (
    <>
      <section className="settings-section">
        <h2>Members</h2>
        <p className="tech-stack-description">
          Manage who belongs to your organization and their roles.
        </p>

        {membersMsg && <div className="settings-action-msg">{membersMsg}</div>}
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
                  <tr key={m.user_id}>
                    <td>{m.email}</td>
                    <td>
                      {m.role === "owner" ? (
                        <span className="role-badge">{m.role}</span>
                      ) : (
                        <select
                          className="member-role-select"
                          value={m.role ?? "member"}
                          onChange={(e) =>
                            handleUpdateMemberRole(m.user_id, e.target.value)
                          }
                          disabled={
                            m.user_id === userId ||
                            (orgRole !== "owner" && role !== "admin")
                          }
                        >
                          <option value="member">member</option>
                          <option value="admin">admin</option>
                        </select>
                      )}
                    </td>
                    <td>{new Date(m.created_at).toLocaleDateString()}</td>
                    <td>
                      {m.role !== "owner" && m.user_id !== userId && (
                        <button
                          className="vendor-delete-btn"
                          onClick={() => handleRemoveMember(m.user_id)}
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
                    membersPage >= Math.ceil(membersTotal / membersPageSize)
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

      <section className="settings-section">
        <h2>Invitations</h2>
        <p className="tech-stack-description">
          Invite users to join your organization. They will need to create an
          account with the invited email and accept the invite.
        </p>

        {invitesMsg && <div className="settings-action-msg">{invitesMsg}</div>}
        {createdInviteLink && (
          <div
            className="settings-action-msg"
            style={{
              border: "1px solid var(--accent, #2d7)",
              padding: "0.75rem",
              marginBottom: "0.75rem",
            }}
          >
            <pre
              style={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                margin: "0.5rem 0",
                userSelect: "all",
              }}
            >
              {createdInviteLink}
            </pre>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="action-btn" onClick={handleCopyInviteLink}>
                {inviteLinkCopied ? "Copied!" : "Copy link"}
              </button>
              <button
                className="action-btn"
                onClick={() => {
                  setCreatedInviteLink(null);
                  setInviteLinkCopied(false);
                  setInvitesMsg("");
                }}
              >
                Done
              </button>
            </div>
          </div>
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
              onKeyDown={(e) => e.key === "Enter" && handleSendInvite()}
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
                    <td>{inv.email}</td>
                    <td>{inv.role}</td>
                    <td>
                      <span
                        className={`status-badge ${inv.status === "pending" ? "active" : "inactive"}`}
                      >
                        {inv.status}
                      </span>
                    </td>
                    <td>{new Date(inv.expires_at).toLocaleDateString()}</td>
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
                    invitesPage >= Math.ceil(invitesTotal / membersPageSize)
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
    </>
  );
}
