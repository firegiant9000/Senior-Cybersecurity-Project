# Docs

**Current plan:** the Revision 2026-09-29 section of [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md) (milestones S0 to S6). The evidence behind it is [roadmap-review-2026-09.md](roadmap-review-2026-09.md). Every other planning document below is history; where one disagrees with the revision, the revision wins.

Start here:

- [SETUP.md](SETUP.md) — local setup for new contributors (Docker and bare-metal)
- [COMMANDS.md](COMMANDS.md) — Make targets and everyday commands
- [DATA_SOURCE_STATUS.md](DATA_SOURCE_STATUS.md) — which feeds are live, cached, or static

Architecture:

- [architecture/anomaly-detection-design-note.md](architecture/anomaly-detection-design-note.md)
- [architecture/inventory_csv_format.md](architecture/inventory_csv_format.md) — canonical asset inventory CSV
- [../agent/README.md](../agent/README.md) — the Go host scanner and its wire contract
- [m365_integration_notes.md](m365_integration_notes.md) — Microsoft 365 inventory spike

Security and privacy:

- [security/agent_enrollment.md](security/agent_enrollment.md) — per-host tokens, rotation, revocation, replay window
- [security/agent_release_signing.md](security/agent_release_signing.md) — GPG-signed release manifest (never exercised; superseded by milestone S1, keyless artifact attestations plus a CycloneDX SBOM)
- Threat model and authorization classification: planned as `security/threat_model.md` (S3) and the route-classification table (S4); neither exists yet
- [security/privacy.md](security/privacy.md) and [security/pii_inventory.md](security/pii_inventory.md)

Project history (capstone planning and execution records, kept as-is):

- Month plans: [month_1_execution_plan.md](month_1_execution_plan.md), [month_2_execution_plan.md](month_2_execution_plan.md), [month_3_execution_plan.md](month_3_execution_plan.md), [month_4_execution_plan.md](month_4_execution_plan.md)
- [hacker_tracker_6_month_development_plan.md](hacker_tracker_6_month_development_plan.md): Months 1 to 4 are the build record; Months 5 and 6 are superseded (statuses in its revision note)
- Implementation plans and closeouts: `implementation-plan-*.md`, `month_*_closeout.md`, `manual_test_month*.md`, `SCRUM-*`, `mentor-feedback-plan.md`, `intake_gating_audit.md`, `BROKEN_TEST_REMEDIATION.md`: all HISTORICAL, work merged
- [agent_auto_update.md](agent_auto_update.md): design only, DEFERRED until two attested releases exist
- [project-history/](project-history/) — early per-feed READMEs and ingestion notes from the first weeks

Screenshots go in [screenshots/](screenshots/).
