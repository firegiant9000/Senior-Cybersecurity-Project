import { useNavigate } from "react-router-dom";
import "../Dashboard.css";
import "../components/dashboard/DashboardHeader.css";
import "./TrustPage.css";

export default function PrivacyPage() {
  const navigate = useNavigate();

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Privacy</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
        </div>
      </header>

      <div className="trust-page">
        <p className="trust-page-intro">
          Plain-language summary of how Hacker Tracker handles your data. The
          authoritative technical inventory lives in our public PII inventory
          and source-code repository — this page mirrors it in plain English.
        </p>

        <div className="trust-card">
          <h2>What we collect</h2>
          <ul>
            <li>
              <strong>Account info:</strong> email and (optional) display name.
              Used to log you in and tie your actions to your organization.
            </li>
            <li>
              <strong>Organization profile:</strong> the company name, domains,
              and tech stack you provide during onboarding — used to match
              threat intelligence to your environment.
            </li>
            <li>
              <strong>Activity:</strong> anonymized request logs and audit
              entries — which API your account called, when, and whether it
              succeeded. Retained for 12 months.
            </li>
          </ul>

          <h2>What we do not collect</h2>
          <ul>
            <li>We do not install agents on your endpoints.</li>
            <li>We do not scan your network without explicit consent.</li>
            <li>We do not sell or share your data with advertisers.</li>
            <li>
              We do not store your password directly — authentication is
              delegated to Firebase Auth.
            </li>
          </ul>

          <h2>Where your data lives</h2>
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Role</th>
                <th>Region</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Firebase Auth</td>
                <td>Authentication</td>
                <td>Google global</td>
              </tr>
              <tr>
                <td>Render</td>
                <td>Backend + managed PostgreSQL</td>
                <td>US East (Ohio)</td>
              </tr>
              <tr>
                <td>Firebase Hosting</td>
                <td>Static frontend assets</td>
                <td>Google global</td>
              </tr>
              <tr>
                <td>Sentry</td>
                <td>Error reports (scrubbed)</td>
                <td>US</td>
              </tr>
            </tbody>
          </table>

          <h2>Your rights</h2>
          <ul>
            <li>
              <strong>Export:</strong> an admin can call{" "}
              <code>GET /api/v1/organizations/{"{id}"}/export</code> for a JSON
              dump of every row we hold about your org.
            </li>
            <li>
              <strong>Delete:</strong> an admin can call{" "}
              <code>DELETE /api/v1/organizations/{"{id}"}</code> to purge the
              organization — every referencing table is iterated explicitly.
            </li>
            <li>
              <strong>Correct:</strong> edit your org profile from the in-app
              settings page.
            </li>
          </ul>

          <h2>Error reports</h2>
          <p>
            Before any error event leaves our infrastructure for Sentry, we
            redact: email addresses, <code>Authorization</code> headers,
            cookies, hostnames, and any field name containing{" "}
            <code>token</code>, <code>secret</code>, <code>password</code>,{" "}
            <code>api_key</code>, or <code>apikey</code>.
          </p>

          <h2>Honest limits</h2>
          <p>
            Hacker Tracker is an early-stage product. We do not currently hold
            SOC 2 or ISO 27001 certifications. Treat this tool as
            decision-support, not a system of record. See our{" "}
            <a href="/data-handling">data handling page</a> for the
            per-dataset transparency report.
          </p>
        </div>
      </div>
    </div>
  );
}
