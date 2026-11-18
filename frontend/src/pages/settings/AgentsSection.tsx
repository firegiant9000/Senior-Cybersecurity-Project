import {
  useState,
  useEffect,
  useCallback,
  useRef,
  type ComponentRef,
} from "react";
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
import {
  findRowAction,
  focusOrder,
} from "../../components/shared/focusAfterRemoval";

export default function AgentsSection() {
  const rootRef = useRef<HTMLElement>(null);
  const headingRef = useRef<ComponentRef<"h2">>(null);
  const copyTokenRef = useRef<HTMLButtonElement>(null);
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
        "Token rotated. The old token works for up to 24h; copy the new one now.",
      );
      await loadAgents();
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
      await loadAgents();
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
      await loadAgents();
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
      body: `Issue a new token for ${a.name}? The current token keeps working for up to 24 hours.`,
      confirmLabel: "Rotate",
      tone: "default",
      onConfirm: () => handleRotateAgent(a.id),
      // Never "I've saved it": that button discards the one-time token.
      returnFocus: () => copyTokenRef.current ?? headingRef.current,
    });

  const confirmEndGrace = (a: Agent) => {
    const ids = agentsList.map((x) => x.id);
    return confirm({
      title: "End grace period",
      body: `Stop accepting the old token for ${a.name} now? Agents still using it will fail to report.`,
      confirmLabel: "End grace period",
      tone: "danger",
      onConfirm: () => handleEndGrace(a.id),
      returnFocus: () =>
        findRowAction(
          rootRef.current,
          focusOrder(ids, a.id),
          "end-grace",
        ) ?? headingRef.current,
    });
  };

  const confirmRevoke = (a: Agent) => {
    const ids = agentsList.map((x) => x.id);
    return confirm({
      title: "Revoke agent",
      body: `Revoke ${a.name}? This also revokes every linked token in its rotation chain, older and newer, including any new token. Tokens rotated before linking was added are not covered: revoke those separately. The host must be re-enrolled. To cut off only the old token, use End grace now instead.`,
      confirmLabel: "Revoke",
      tone: "danger",
      onConfirm: () => handleRevokeAgent(a.id),
      returnFocus: () =>
        findRowAction(
          rootRef.current,
          focusOrder(ids, a.id),
          "revoke",
        ) ?? headingRef.current,
    });
  };

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
    <section className="settings-section" ref={rootRef}>
      <h2 ref={headingRef} tabIndex={-1}>
        Scanner Agents
      </h2>
      <p className="tech-stack-description">
        Enroll read-only host scanner agents. Each agent gets its
        own bearer token shown only once at enrollment — store it
        securely and re-enroll if it is lost. Rotate to replace a
        token (the old one keeps working for up to 24 hours; rotate the
        new one, not the old). If the old token may have leaked,
        use &ldquo;End grace now&rdquo; to cut off only that token.
        Revoke cuts off the agent and every linked token in its rotation chain
        (tokens rotated before linking was added are not covered:
        revoke those separately).
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
            <button
              className="action-btn"
              ref={copyTokenRef}
              onClick={handleCopyToken}
            >
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
              <tr key={a.id} data-row-id={a.id}>
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
                        data-action="rotate"
                        onClick={() => confirmRotate(a)}
                        title="Rotate token"
                      >
                        Rotate
                      </button>
                    )}
                  {a.status === "grace" && (
                    <button
                      className="action-btn"
                      data-action="end-grace"
                      onClick={() => confirmEndGrace(a)}
                      title="End grace now"
                    >
                      End grace now
                    </button>
                  )}
                  {a.status !== "revoked" && (
                    <button
                      className="vendor-delete-btn"
                      data-action="revoke"
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
