import { useState, useEffect, useCallback } from "react";
import {
  Agent,
  AgentTokenIssued,
  listAgents,
  enrollAgent,
  rotateAgent,
  endAgentGrace,
  revokeAgent,
} from "../../api/agents";
import { useConfirm } from "../../components/shared/ConfirmDialog";

export default function AgentsSection() {
  // Agent enrollment state (Month 4 Phase 2)
  const [agentsList, setAgentsList] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState("");
  const [agentsMsg, setAgentsMsg] = useState("");
  const [agentName, setAgentName] = useState("");
  // The raw token is shown exactly once, right after enroll/rotate.
  const [issuedToken, setIssuedToken] = useState<AgentTokenIssued | null>(null);
  const [copied, setCopied] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  const loadAgents = useCallback(async () => {
    setAgentsLoading(true);
    setAgentsError("");
    try {
      const data = await listAgents();
      setAgentsList(data.items ?? []);
    } catch {
      setAgentsError("Failed to load agents");
    } finally {
      setAgentsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const handleEnrollAgent = async () => {
    if (!agentName.trim()) return;
    setAgentsError("");
    setAgentsMsg("");
    setCopied(false);
    try {
      const issued = await enrollAgent(agentName.trim());
      setIssuedToken(issued);
      setAgentName("");
      setAgentsMsg("Agent enrolled. Copy the token now — it won't be shown again.");
      loadAgents();
    } catch (err) {
      setAgentsError(
        err instanceof Error ? err.message : "Failed to enroll agent",
      );
    }
  };

  const handleRotateAgent = async (agentId: number) => {
    setAgentsError("");
    setAgentsMsg("");
    setCopied(false);
    try {
      const issued = await rotateAgent(agentId);
      setIssuedToken(issued);
      setAgentsMsg(
        "Token rotated. The old token works for 24h; copy the new one now.",
      );
      loadAgents();
    } catch (err) {
      setAgentsError(
        err instanceof Error ? err.message : "Failed to rotate agent",
      );
    }
  };

  const handleEndGrace = async (agentId: number) => {
    setAgentsError("");
    setAgentsMsg("");
    try {
      await endAgentGrace(agentId);
      setAgentsMsg("Grace ended. The old token no longer works.");
      loadAgents();
    } catch (err) {
      setAgentsError(
        err instanceof Error ? err.message : "Failed to end the grace window",
      );
    }
  };

  const handleRevokeAgent = async (agentId: number) => {
    setAgentsError("");
    try {
      await revokeAgent(agentId);
      setAgentsMsg("Agent revoked.");
      loadAgents();
    } catch (err) {
      setAgentsError(
        err instanceof Error ? err.message : "Failed to revoke agent",
      );
    }
  };

  // The handlers above catch API failures into agentsError, so a rejected call
  // never reaches the dialog (which would swallow it and close silently).
  const confirmRotate = (a: Agent) =>
    confirm({
      title: "Rotate agent token",
      body: `Issue a new token for ${a.name}? The current token keeps working for 24 hours.`,
      confirmLabel: "Rotate",
      tone: "danger",
      onConfirm: () => handleRotateAgent(a.id),
    });

  const confirmEndGrace = (a: Agent) =>
    confirm({
      title: "End grace period",
      body: `Stop accepting the old token for ${a.name} now? Agents still using it will fail to report.`,
      confirmLabel: "End grace period",
      tone: "danger",
      onConfirm: () => handleEndGrace(a.id),
    });

  const confirmRevoke = (a: Agent) =>
    confirm({
      title: "Revoke agent",
      body: `Revoke ${a.name}? It can no longer report scans.`,
      confirmLabel: "Revoke",
      tone: "danger",
      onConfirm: () => handleRevokeAgent(a.id),
    });

  const handleCopyToken = async () => {
    if (!issuedToken) return;
    try {
      await window.navigator.clipboard.writeText(issuedToken.raw_token);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="settings-section">
      <h2>Scanner Agents</h2>
      <p className="tech-stack-description">
        Enroll read-only host scanner agents. Each agent gets its
        own bearer token shown only once at enrollment — store it
        securely and re-enroll if it is lost. Rotate to replace a
        token (the old one keeps working for 24 hours; rotate the
        new one, not the old). If the old token may have leaked,
        use &ldquo;End grace now&rdquo; to cut off only that token.
        Revoke cuts off the agent and every token rotated from it
        (tokens rotated before this update may not be linked).
      </p>

      {agentsMsg && <div className="settings-action-msg">{agentsMsg}</div>}
      {agentsError && (
        <div
          className="settings-error"
          style={{
            whiteSpace: "pre-line",
            marginBottom: "0.75rem",
          }}
        >
          {agentsError}
        </div>
      )}

      {issuedToken && (
        <div
          className="settings-action-msg"
          style={{
            border: "1px solid var(--accent, #2d7)",
            padding: "0.75rem",
            marginBottom: "0.75rem",
          }}
        >
          <strong>
            Token for “{issuedToken.agent.name}” — copy it now, it
            will not be shown again:
          </strong>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              margin: "0.5rem 0",
            }}
          >
            {issuedToken.raw_token}
          </pre>
          <p style={{ margin: "0.25rem 0" }}>Install / upload with:</p>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              margin: "0.5rem 0",
            }}
          >
            hacker-tracker scan --upload --api-key{" "}
            {issuedToken.raw_token}
          </pre>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button className="action-btn" onClick={handleCopyToken}>
              {copied ? "Copied!" : "Copy token"}
            </button>
            <button
              className="action-btn"
              onClick={() => {
                setIssuedToken(null);
                setCopied(false);
              }}
            >
              I've saved it
            </button>
          </div>
        </div>
      )}

      <div className="vendor-add-form">
        <div className="vendor-input-wrapper">
          <input
            type="text"
            placeholder="Agent name (e.g. web-01)"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleEnrollAgent()}
          />
        </div>
        <button
          className="action-btn"
          onClick={handleEnrollAgent}
          disabled={!agentName.trim()}
        >
          Enroll new agent
        </button>
      </div>

      {agentsLoading ? (
        <p className="settings-loading">Loading agents...</p>
      ) : agentsList.length === 0 ? (
        <p className="vendor-empty">No agents enrolled.</p>
      ) : (
        <table className="vendor-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Token prefix</th>
              <th>Status</th>
              <th>Last used</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {agentsList.map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td>
                <td>
                  <code>ht_{a.token_prefix}_…</code>
                </td>
                <td>
                  <span
                    className={`status-badge ${a.status === "active" ? "active" : "inactive"}`}
                  >
                    {a.status}
                  </span>
                </td>
                <td>
                  {a.last_used_at
                    ? new Date(a.last_used_at).toLocaleString()
                    : "never"}
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {a.status !== "revoked" &&
                    a.status !== "expired" &&
                    a.status !== "grace" && (
                      <button
                        className="action-btn"
                        onClick={() => confirmRotate(a)}
                        title="Rotate token"
                      >
                        Rotate
                      </button>
                    )}
                  {a.status === "grace" && (
                    <button
                      className="action-btn"
                      onClick={() => confirmEndGrace(a)}
                      title="End grace now"
                    >
                      End grace now
                    </button>
                  )}
                  {a.status !== "revoked" && (
                    <button
                      className="vendor-delete-btn"
                      onClick={() => confirmRevoke(a)}
                      title="Revoke agent"
                      aria-label={`Revoke ${a.name}`}
                    >
                      &times;
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {confirmDialog}
    </section>
  );
}
