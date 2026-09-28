# Docs

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
- [security/agent_release_signing.md](security/agent_release_signing.md) — GPG-signed release manifest
- [security/privacy.md](security/privacy.md) and [security/pii_inventory.md](security/pii_inventory.md)

Project history (capstone planning and execution records, kept as-is):

- Month plans: [month_1_execution_plan.md](month_1_execution_plan.md), [month_2_execution_plan.md](month_2_execution_plan.md), [month_3_execution_plan.md](month_3_execution_plan.md), [month_4_execution_plan.md](month_4_execution_plan.md)
- [hacker_tracker_6_month_development_plan.md](hacker_tracker_6_month_development_plan.md), [PRODUCT_VIABILITY_ROADMAP.md](PRODUCT_VIABILITY_ROADMAP.md)
- Implementation plans and closeouts: `implementation-plan-*.md`, `month_*_closeout.md`, `manual_test_month*.md`
- [project-history/](project-history/) — early per-feed READMEs and ingestion notes from the first weeks

Screenshots go in [screenshots/](screenshots/).
