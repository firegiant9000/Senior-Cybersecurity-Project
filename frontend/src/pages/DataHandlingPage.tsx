import { useNavigate } from "react-router-dom";
import "../Dashboard.css";
import "../components/dashboard/DashboardHeader.css";
import "./TrustPage.css";
import { useDataStatus } from "../hooks/useDataStatus";
import SourceBadge from "../components/shared/SourceBadge";
import { useAuth } from "../context/AuthContext";

export default function DataHandlingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { items, loading, error } = useDataStatus();

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Data Handling</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate(user ? "/overview" : "/")}>
            Back
          </button>
        </div>
      </header>

      <div className="trust-page">
        <p className="trust-page-intro">
          Live transparency report. Every dashboard widget pulls from one of
          the datasets below. Each is labeled <strong>Live</strong>,{" "}
          <strong>Static</strong>, <strong>Mocked</strong>, or{" "}
          <strong>Pending</strong> so you can tell at a glance whether the
          number is being refreshed against an upstream source or is a frozen
          snapshot.
        </p>

        <div className="trust-card">
          <h2>Per-dataset status</h2>
          {loading && <p>Loading…</p>}
          {error && (
            <p style={{ color: "#d32f2f" }}>
              Couldn&apos;t load the registry: {error}
            </p>
          )}
          {!loading && !error && (
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Status</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.key}>
                    <td>{row.label}</td>
                    <td>
                      <SourceBadge
                        datasetKey={row.key}
                        fallbackStatus={row.status}
                        fallbackSource={row.source}
                      />
                    </td>
                    <td>
                      {row.source}
                      {row.notes ? (
                        <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                          {row.notes}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h2>How this list stays honest</h2>
          <p>
            The list comes from a single registry that every dashboard widget
            must be listed in, and the badges you see on the dashboard read
            from that same registry. If this page and a badge ever disagree,
            the registry is right and we fix the other.
          </p>

          <h2>Optional host scanner</h2>
          <p>
            One data source is opt-in and host-side: the read-only inventory
            agent. Nothing is collected from a host until an admin enrolls an
            agent and you run the binary there. It collects installed packages,
            running services, OS/host metadata, and (only with{" "}
            <code>--include-ports</code>) listening ports — and never file
            contents, secrets, credentials, or browser data. Inspect exactly
            what would be sent with <code>scan --print</code> before uploading.
            See <a href="/privacy">Privacy</a> for the full disclosure.
          </p>

          <h2>Readiness check (no login)</h2>
          <p>
            When the site operator turns it on, a logged-out visitor can check
            their email domain and take a short readiness quiz (the quiz is not
            available yet). The domain is looked up in public DNS and is not
            saved or logged (the result is reused for up to 15 minutes to
            avoid repeat lookups). Quiz answers are scored and not saved. The
            only thing saved to the database is an anonymous count of each
            step per day. Your IP address appears in the server&apos;s request
            logs and is used for rate limiting, as on every request. See{" "}
            <a href="/privacy">Privacy</a> for details.
          </p>

          <h2>Related</h2>
          <ul>
            <li>
              <a href="/privacy">Privacy</a> — plain-language summary of what
              personal data we collect.
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
