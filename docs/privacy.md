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

## What we do *not* collect

- We do not install agents on your endpoints.
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
