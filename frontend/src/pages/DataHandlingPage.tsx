import { useNavigate } from "react-router-dom";
import "../Dashboard.css";
import "../components/dashboard/DashboardHeader.css";
import "./TrustPage.css";
import { useDataStatus } from "../hooks/useDataStatus";
import SourceBadge from "../components/shared/SourceBadge";

export default function DataHandlingPage() {
  const navigate = useNavigate();
  const { items, loading, error } = useDataStatus();

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Data Handling</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate("/")}>
            Back to Dashboard
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
            The list is generated from a single registry in our backend
            (<code>backend/app/services/data_status.py</code>). Any new widget
            must register here, and the frontend reads from the same endpoint
            (<code>GET /api/v1/data-status</code>) to render its badges. If
            the registry, this page, and the dashboard ever disagree, the
            registry wins.
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
