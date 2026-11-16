# Readiness quiz: source forms

The readiness quiz questions (`backend/app/data/readiness/questions_v1.json`) come from what real cyber insurance applications ask. This file records the forms we used and how each question was chosen.

The forms are the insurers' copyright. We link to them and do not copy them into this repo. Quiz wording is our own; no question copies an insurer's wording.

## Forms

| Label | Insurer | Form name / number | Link | Opened |
|---|---|---|---|---|
| Form A | AXIS Insurance | AXIS Cyber Application for Small Business, AXIS 1012985 1022 | [PDF](https://www.axiscapital.com/docs/default-source/default-document-library/axis-cyber-application-for-small-business-axis-1012985-1022.pdf?sfvrsn=f075e7a9_0) | 2026-11-13 |
| Form B | CFC Underwriting | Cyber Proactive Response Insurance application form, US (one-page application, v12) | [PDF](https://www.cfc.com/media/clyfotxn/cyber-one-page-application-us-v12.pdf) | 2026-11-13 |
| Form C | Corvus Insurance | Smart Cyber Insurance Application (hosted by broker Alliant; file dated 07/21/22) | [PDF](https://alliant.com/media/0vzftbhk/corvus-smart-cyber-application_072122.pdf) | 2026-11-13 |

Notes:
- Form A is the only one labelled as a small-business version. Forms B and C are short-form applications used for smaller accounts.
- The Form C copy is a broker-hosted PDF, not the insurer's own site. Corvus does not publish its application directly.

## Control tally

✓ = the form asks about this control. Section or question numbers are given where the form numbers them.

| Control | Form A | Form B | Form C | Count | Candidate |
|---|---|---|---|---|---|
| MFA for remote access | ✓ 20a | ✓ | ✓ 13 | 3 | Yes |
| Regular backups / backup frequency | ✓ 33–34 | ✓ | ✓ 9 | 3 | Yes |
| Backups protected or kept offline / unchangeable | ✓ 36–37, 39 | ✓ | ✓ 11 | 3 | Yes |
| Staff security / phishing training | ✓ 29 | ✓ | ✓ 17 | 3 | Yes |
| Encryption of stored data / devices | ✓ 28 | ✓ (database encryption) | ✓ 16 | 3 | Yes |
| MFA for email | – | ✓ | ✓ 15 | 2 | Yes |
| MFA for admin accounts | ✓ 20b | – | ✓ 14 | 2 | Yes |
| Backup restore tested | ✓ 40 | ✓ | – | 2 | Yes |
| Endpoint protection (antivirus or similar) | ✓ 18 | ✓ | – | 2 | Yes |
| Endpoint detection & response (EDR) | ✓ 22 | ✓ | – | 2 | Yes |
| Security monitoring / SOC | ✓ 25 | ✓ | – | 2 | Yes |
| Patching / software updates | ✓ 21, 24 | ✓ | – | 2 | Yes |
| Incident response plan | ✓ 15a | ✓ | – | 2 | Yes |
| Payment / bank-detail change verification | ✓ 49a | – | ✓ 21 | 2 | Yes |
| Email filtering | – | ✓ | ✓ 8 | 2 | Yes |
| Phishing simulations | ✓ 30 | ✓ | – | 2 | Yes |
| Remote Desktop (RDP) / remote access tools in use | ✓ 19 | – | ✓ 12 | 2 | Yes |
| Firewalls | ✓ 27b | ✓ | – | 2 | Yes |
| PCI DSS / payment card handling | ✓ 5–9 | – | ✓ 19–20 | 2 | Yes |
| Prior cyber incidents | ✓ 61–68 | ✓ | ✓ 22–24 | 3 | No: history, not a control |
| Email authentication (SPF / DKIM / DMARC) | ✓ 23 | ✓ | – | 2 | Yes |
| End-of-life software | ✓ 26 | – | – | 1 | No |
| Business continuity / disaster recovery plan | ✓ 13–14 | – | – | 1 | No |
| Written security policy | ✓ 11 | – | – | 1 | No |
| Log management / SIEM | ✓ 27 | – | – | 1 | No |
| Anti-fraud training | ✓ 51 | – | – | 1 | No |

## Selected questions

| Question id | Control | Forms | Weight | Intake field |
|---|---|---|---|---|
| `mfa_email` | MFA for email | B, C | 2 | `mfa_enabled` |
| `mfa_remote_access` | MFA for remote access | A, B, C | 3 | |
| `mfa_admin_accounts` | MFA for admin accounts | A, C | 2 | |
| `backups_regular` | Regular backups | A, B, C | 3 | `backup_strategy` |
| `backups_out_of_reach` | Backups offline / unchangeable | A, B, C | 3 | |
| `backups_restore_tested` | Backup restore tested | A, B | 2 | |
| `security_software` | Endpoint protection | A, B | 2 | `endpoint_protection` |
| `software_updates` | Patching | A, B | 2 | |
| `staff_training` | Staff security training | A, B, C | 3 | (new; not collected today) |
| `incident_response_plan` | Incident response plan | A, B | 2 | `incident_response_plan` |
| `payment_verification` | Payment verification | A, C | 2 | |
| `device_encryption` | Encryption | A, B, C | 3 | |

Weight rule: 3 when all three forms ask it. None of the forms marks a question as required, so this is the only way a question gets weight 3. Weight 2 when two forms ask it. No weight-1 questions were selected.

## Candidates left out, and why

| Control | Reason |
|---|---|
| EDR / security monitoring / SOC | An owner can rarely tell EDR from antivirus, and `security_software` already covers the basic question. A good candidate for v2 if try-outs show owners can answer it. |
| Email filtering | Usually built into Microsoft 365 or Google Workspace, so most owners would answer "yes" without knowing. Low signal. |
| Phishing simulations | Folded into `staff_training`. Its help text names practice scam emails as one form of training. |
| RDP / remote access tools | An inventory question, not a yes/no control. The risk it points at is covered by `mfa_remote_access`. |
| Firewalls | Almost every office router has one. Owners can't judge whether it is configured well. |
| PCI DSS | Applies only to businesses that take cards directly, and is usually handled by the payment processor. |
| SPF / DKIM / DMARC | Requires DNS knowledge. Not answerable without help. |
| Prior incidents | History, not a control. There is no "first step" to give. |
