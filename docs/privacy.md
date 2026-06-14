# Privacy Promise

This is the user-facing summary of how Hacker Tracker handles your data. The
authoritative technical inventory lives in [pii_inventory.md](pii_inventory.md);
this doc says the same thing in plain language and is mirrored on the in-app
`/privacy` page.

---

## What we collect

- **Account info:** email and (optional) display name. Used to log you in and
  associate your actions with your organization.
- **Organization profile:** the company name, domains, and tech stack you
  enter during onboarding. We use this to match threat intelligence to your
  actual environment.
- **Activity:** anonymized request logs and audit entries — which API your
  account called, when, and whether it succeeded. Kept for 12 months.
- **Host inventory (optional agent):** if *you* choose to install and enroll
  the read-only host scanner (see below), it sends installed-package
  names/versions, running service names, OS/hostname/arch, and — only when you
  pass `--include-ports` — listening port numbers. Used solely to match your
  inventory against KEV/NVD and surface relevant CVEs.

## The optional host scanner

The scanner is **opt-in**: nothing is collected from a host until an admin in
your org enrolls an agent and you run the binary on that host with the token.
It is **read-only** — it never writes, installs, or changes anything.

**What it collects:** installed package names + versions (`dpkg`/`rpm`), running
service names (`systemctl`), OS/hostname/architecture, and listening ports
(**only** with `--include-ports`).

**What it never collects:**

- file **contents**, documents, or source code,
- environment variables, secrets, tokens, or credentials,
- browser history, cookies, or saved passwords.

You can review exactly what would be sent with `scan --print` **before** any
upload. Per-host enrollment tokens are stored hashed (never recoverable) and can
be rotated or revoked from the dashboard at any time. Full field-by-field
disclosure and the enrollment/revocation flow live in
[agent_enrollment.md](agent_enrollment.md) and [../agent/README.md](../agent/README.md).

## What we do *not* collect

- We do not install or run the host scanner without your explicit action —
  it is opt-in, per-host, and read-only (see above).
- We do not scan your network without explicit consent.
- We do not sell or share your data with advertisers.
- We do not store your password directly — authentication is delegated to
  Firebase Auth.

## Where your data lives

| Provider          | Role                                       | Region                |
|-------------------|--------------------------------------------|-----------------------|
| Firebase Auth     | Authentication                             | Google global         |
| Render            | Backend + managed PostgreSQL               | US East (Ohio)        |
| Firebase Hosting  | Static frontend assets                     | Google global         |
| Sentry            | Error reports (scrubbed)                   | US                    |

We do not transfer data outside the United States except where the provider
operates a global CDN for static assets only.

## Your rights

- **Export.** An admin in your organization can call
  `GET /api/v1/organizations/{id}/export` to retrieve a JSON dump of every
  row we hold about your org.
- **Delete.** An admin can call `DELETE /api/v1/organizations/{id}` to purge
  the organization. The deletion iterates every table explicitly — no orphan
  rows. The deletion event itself is logged for audit, then ages out after 12
  months.
- **Correct.** Edit your org profile from the in-app settings page.

If you need help exercising these rights, email the project owner
(see [README.md](../README.md)).

## What we scrub from error reports

Before any error event leaves our infrastructure for Sentry, the following are
redacted:

- Email addresses (any field, any case)
- `Authorization` headers and any field whose name contains `token`, `secret`,
  `password`, `api_key`, or `apikey`
- Hostnames and cookies

See [pii_inventory.md](pii_inventory.md) for the full scrubber spec.

## Honest limits

Hacker Tracker is an early-stage product. We do not currently hold SOC 2 or
ISO 27001 certifications. Treat this tool as decision-support, not a system
of record. See [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md)
for the full list of what is and is not in scope today.

## Updates

Material changes to this document are announced via the in-app `/privacy` page
and the project changelog. The git history of this file is the authoritative
record of every revision.
