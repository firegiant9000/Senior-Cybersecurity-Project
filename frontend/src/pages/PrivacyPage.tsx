import { useNavigate } from "react-router-dom";
import "../Dashboard.css";
import "../components/dashboard/DashboardHeader.css";
import "./TrustPage.css";
import { useAuth } from "../context/AuthContext";

export default function PrivacyPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Privacy</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate(user ? "/overview" : "/")}>
            Back
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
              <strong>Activity:</strong> request logs (which include your IP
              address or your network&apos;s) and audit entries — which API
              your account called, when, and whether it succeeded. Audit
              entries are kept for 12 months.
            </li>
            <li>
              <strong>Asset inventory:</strong> CSV uploads, cloud-integration
              (e.g. Microsoft 365) syncs, or the optional read-only host scanner
              you choose to install. Hostnames, IPs, OS, and software
              vendor/product/version land in your org-scoped{" "}
              <code>assets</code> table. Used only to match your inventory
              against KEV/NVD and surface relevant CVEs. We never sync these
              without an explicit action from your admin.
            </li>
            <li>
              <strong>Integration tokens:</strong> when you connect Microsoft
              365 / Entra, the OAuth access and refresh tokens are stored
              encrypted at rest (Fernet) and only used to call Microsoft Graph
              on your behalf.
            </li>
          </ul>

          <h2>The optional host scanner</h2>
          <p>
            The host scanner is <strong>opt-in</strong>: nothing is collected
            from a host until an admin enrolls an agent and you run the binary
            on that host with the token. It is <strong>read-only</strong> — it
            never writes, installs, or changes anything.
          </p>
          <ul>
            <li>
              <strong>Collects:</strong> installed package names + versions
              (<code>dpkg</code>/<code>rpm</code>), running service names
              (<code>systemctl</code>), OS/hostname/architecture, and listening
              ports (only with <code>--include-ports</code>).
            </li>
            <li>
              <strong>Never collects:</strong> file contents, documents, source
              code, environment variables, secrets, tokens, credentials, browser
              history, cookies, or saved passwords.
            </li>
            <li>
              Review exactly what would be sent with <code>scan --print</code>{" "}
              before any upload. Per-host tokens are stored hashed and can be
              rotated or revoked from the dashboard at any time.
            </li>
          </ul>

          <h2>The readiness check (no login)</h2>
          <p>
            The readiness check lets you check your email domain and take a
            short quiz without an account. It is off unless the site operator
            turns it on. When it is on:
          </p>
          <ul>
            <li>
              <strong>The domain you type</strong> is looked up in public DNS
              (its SPF and DMARC records) and is not stored or logged. The
              server keeps it in memory for up to 15 minutes so a repeat check
              doesn&apos;t query DNS again, then forgets it. It is not sent to
              the domain-check providers listed below.
            </li>
            <li>
              <strong>Your quiz answers</strong> are scored and shown back to
              you. They are not stored or logged.
            </li>
            <li>
              <strong>Only anonymous step counts are kept:</strong> how many
              times each step (such as starting the quiz) happened each day,
              with no visitor ID, IP address, domain or answer attached.
            </li>
            <li>
              <strong>Your IP address</strong> is handled as on every other
              request: it appears in the server&apos;s request logs and is used
              for rate limiting.
            </li>
          </ul>

          <h2>What we do not collect</h2>
          <ul>
            <li>
              We do not install or run the host scanner without your explicit
              action — it is opt-in, per-host, and read-only (see above).
            </li>
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
                <td>US West (Oregon)</td>
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
              <tr>
                <td>Google Gemini API</td>
                <td>AI summary (org-level fields and findings only, no user identifiers)</td>
                <td>Google global</td>
              </tr>
              <tr>
                <td>HIBP, Shodan, AlienVault OTX, crt.sh</td>
                <td>External domain checks (your organization&apos;s domain name or its public address only)</td>
                <td>Each provider&apos;s own</td>
              </tr>
            </tbody>
          </table>

          <h2>Your rights</h2>
          <ul>
            <li>
              <strong>Export:</strong> an organisation admin can ask the site
              operator for a JSON file of your organisation&apos;s data: its
              profile, domains, vendors, assets and installed software, finding
              statuses and snapshots, scan runs, upload records, AI summaries
              and feedback, assessment submissions, memberships and invitations.
              It does not include login accounts, audit records, per-asset
              vulnerability matches or integration tokens.
            </li>
            <li>
              <strong>Delete:</strong> an organisation admin can ask the site
              operator to permanently delete the organisation and that same
              data. Member login accounts are not deleted; they are detached
              from the organisation.
              Audit records are kept, including a
              record of the deletion itself, for the retention period under
              Activity above.
            </li>
            <li>
              <strong>Correct:</strong> edit your org profile from the in-app
              settings page.
            </li>
          </ul>
          <p>
            To make either request, contact the site operator from the account
            that administers your organisation.
          </p>

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
