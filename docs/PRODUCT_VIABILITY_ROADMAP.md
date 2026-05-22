# Product Viability Roadmap

This document is the public commitment record for what Hacker Tracker can and
cannot do today, and what we are working toward. It is intentionally honest:
prospects, design partners, and reviewers should be able to read this and know
exactly where we are.

Companion docs:
- [DATA_SOURCE_STATUS.md](DATA_SOURCE_STATUS.md) — per-widget data backing
- [pii_inventory.md](pii_inventory.md) — what personal data we collect/log
- [privacy.md](privacy.md) — user-facing privacy promise

---

## Where we are today (Month 1 — May 2026)

**Position:** early-stage MSP/SMB-facing cyber threat intelligence platform.
Out of academic prototype, not yet generally available.

**Real, working capabilities:**
- Live NVD CVE ingestion with severity / KEV labelling.
- Per-org vendor matching against CISA KEV.
- Org onboarding, role-based access (Firebase + role gates).
- Static IC3 (FBI Internet Crime Complaint Center) aggregate analytics.
- Composite CVSS + KEV risk scoring per CVE.
- AI-generated executive summaries grounded in the above.

**Honest limits:**
- IC3 incident data is a curated static snapshot of the 2023 annual report,
  not a live feed. Labelled as such everywhere it appears.
- Domain reputation checks (HIBP / Shodan / OTX) are *not* shipped yet — keys
  are wired but the route is gated behind Month 1 Phase E.
- No automated retention / data-lifecycle cron yet (Month 4).
- No SOC 2 or formal compliance certification. Treat us as a research-grade
  decision-support tool, not a system of record.

---

## Roadmap

### Month 1 — Stabilize + Foundations (current)
- CI gating, Sentry observability, structured logging.
- Demo-mode segregation per organization.
- Data lifecycle endpoints (DELETE org, export org).
- Data-source transparency labels on every widget.
- Trust pack (this document).

### Month 2 — MSP-shaped onboarding + per-client views
- Sub-org / client hierarchy for MSPs.
- Bulk import of client tech stacks.
- Per-client filtered dashboards.

### Month 3 — Vendor aliasing + real assessment outcomes
- Canonical `vendor_aliases` table — collapse "MSFT" / "Microsoft" / "ms.com".
- Findings export to PDF.
- First paid pilots.

### Month 4 — Retention + scheduling
- Automated retention enforcement (12 scans/asset default).
- Cron-scheduled domain checks with 24h throttling.
- KEV diff alerts (Slack / email).

### Month 5 — Real IC3 ingestion
- Replace static IC3 snapshot with a parser over annual FBI releases.
- Backfill multi-year history.

### Month 6 — Production-readiness
- SOC 2 Type I scoping.
- Customer-managed data export contract.
- Public status page.

---

## Non-goals (deliberately not building)

- Endpoint detection / EDR — we do not install agents.
- Active scanning of customer infrastructure without explicit consent.
- Storing raw exploit code or weaponized payloads.
- A managed-SOC service — we are a tool, not a service.

---

## How to challenge this document

If you read something here that does not match what the product actually does,
file a GitHub issue tagged `trust-pack`. Every claim in this doc should be
falsifiable by inspecting the running system or the codebase.
