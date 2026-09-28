# Assessment Intake Wizard - Stage 1 Complete Analysis

## Executive Summary
This document captures the complete data model, tier progression logic, and API integration points for building the Assessment Intake Wizard frontend.

---

## Part 1: Tier System Overview

The system has 4 tiers with clear progression:

### INCOMPLETE (Default State)
- No requirements met yet
- Starting point for all organizations

### BASIC (Tier 1) - "Basic Risk Profile"
**Description:** Minimum information needed for a baseline risk assessment.

**Requirements (ALL must be met to unlock):**
1. `name` - Organization name (required)
2. `industry` - Industry selection (required)
3. `state` - Primary state (required)
4. `employee_range` - Employee range (required)

**Unlocks:**
- Risk score
- Loss projection
- SMB Risk Advisor
- Executive summary

**Progress:** 4 fields total

### ENHANCED (Tier 2) - "Enhanced Assessment"
**Description:** Adds vendor and domain intelligence for actionable findings.

**Requirements (ALL must be met to unlock):**
1. `vendors` - At least 1 vendor tracked
2. `domains` - At least 1 domain registered
3. `security_controls` - At least 1 security control answered

**Unlocks:**
- Findings report
- Vendor alerts
- Domain checks
- AI summary

**Progress:** 3 fields + all BASIC fields

### COMPREHENSIVE (Tier 3) - "Comprehensive Posture"
**Description:** Full organizational context for highest-confidence analysis.

**Requirements (ALL must be met to unlock):**
1. `revenue` - Revenue range selected
2. `compliance_frameworks` - At least 1 compliance framework selected
3. `data_types` - At least 1 data type selected
4. `uploads` - At least 1 file uploaded
5. `security_controls_depth` - 8+ security controls answered (out of 16)

**Unlocks:**
- Full confidence scores
- Compliance-aware findings
- Detailed loss projections

**Progress:** 5 fields + all BASIC + ENHANCED fields

---

## Part 2: Form Data Model

### Organization Base Fields (stored in Organization table)

```typescript
// REQUIRED for BASIC tier
name: string                                    // 1-255 chars
industry_label: string                         // from enum
primary_state: string                          // 2-letter state code
employee_range: string                         // from enum

// OPTIONAL, needed for higher tiers
revenue_range: string | null                   // from enum
security_controls: Record<string, string> | null  // yes/no/unsure
compliance_frameworks: list[string] | null    // multiple select
data_types: list[string] | null               // multiple select
cloud_providers: list[string] | null          // multiple select
```

### Vendor Tracking (separate Vendor table)
- Created via `POST /api/v1/organizations/{org_id}/vendors`
- Each vendor is a separate record
- Counts toward ENHANCED tier requirement (≥1)

### Domain Tracking (separate OrgDomain table)
- Created via domain check/ingestion endpoints
- Counts toward ENHANCED tier requirement (≥1)

### File Uploads (OrgUpload table)
- Uploaded via `POST /api/v1/organizations/{org_id}/uploads`
- Counts toward COMPREHENSIVE tier requirement (≥1)

---

## Part 3: Enum Values

### Industry Labels (15 options)
```
Finance & Insurance
Healthcare
Tech & Software
Government
Retail & E-Commerce
Education
Manufacturing
Professional Services
Real Estate
Construction
Legal Services
Transportation
Hospitality
Non-Profit
Other
```

### Employee Ranges (6 options)
```
1-10
11-50
51-200
201-500
501-1000
1001+
```

### Revenue Ranges (6 options)
```
Under $1M
$1M-$5M
$5M-$10M
$10M-$50M
$50M-$100M
$100M+
```

### Compliance Frameworks (7 options)
```
HIPAA
PCI-DSS
SOC 2
CMMC
NIST CSF
ISO 27001
None
```

### Data Types (6 options)
```
PII (names, SSNs)
PHI (health records)
Payment card data
Intellectual property
Customer financial data
None of these
```

### Cloud Providers (11 common options)
```
AWS
Azure
GCP
Microsoft 365
Google Workspace
Salesforce
Shopify
QuickBooks
Dropbox
Slack
Zoom
```

### Security Controls (16 total, grouped by category)

**Identity & Access (3)**
1. `mfa_enabled` - MFA enabled for all users
2. `password_policy` - Password policy enforced
3. `sso_in_use` - SSO in use

**Endpoint Protection (3)**
4. `edr_deployed` - EDR/antivirus deployed
5. `devices_encrypted` - Devices encrypted
6. `auto_patching` - Auto-patching enabled

**Email Security (2)**
7. `email_filtering` - Email filtering / gateway
8. `phishing_training` - Phishing training conducted

**Network (3)**
9. `firewall_in_place` - Firewall in place
10. `vpn_remote_access` - VPN for remote access
11. `network_segmentation` - Network segmentation

**Data Protection (3)**
12. `regular_backups` - Regular data backups
13. `backup_testing` - Backup restoration tested
14. `data_classification` - Data classification policy

**Incident Response (2)**
15. `ir_plan_documented` - IR plan documented
16. `ir_plan_tested` - IR plan tested within 12 months

Values: "yes", "no", or "unsure"

---

## Part 4: API Endpoints

### Reading Assessment Status
**GET** `/api/v1/organizations/mine/intake`
- Returns current tier, tier definitions, next tier info, progress percentage
- Used to display progress and requirements
- Response type: `AssessmentIntakeResponse`

### Updating Organization Profile
**PATCH/PUT** `/api/v1/organizations/mine`
- Updates organization fields directly
- Fields supported: `name`, `industry_label`, `primary_state`, `employee_range`, `revenue_range`, `security_controls`, `compliance_frameworks`, `data_types`, `cloud_providers`
- After update, calling `/intake` endpoint recalculates tier status

**Request body example:**
```json
{
  "revenue_range": "$1M-$5M",
  "compliance_frameworks": ["SOC 2", "ISO 27001"],
  "data_types": ["PII (names, SSNs)"],
  "security_controls": {
    "mfa_enabled": "yes",
    "password_policy": "yes",
    "edr_deployed": "unsure"
  }
}
```

### Creating Vendors
**POST** `/api/v1/organizations/{org_id}/vendors`
- Creates a single vendor record
- Required for ENHANCED tier

### Creating File Upload
**POST** `/api/v1/organizations/{org_id}/uploads`
- Uploads a file
- Required for COMPREHENSIVE tier

---

## Part 5: Progress Calculation Logic

The API returns:
```typescript
{
  current_tier: "incomplete" | "basic" | "enhanced" | "comprehensive"
  next_tier: "basic" | "enhanced" | "comprehensive" | null
  next_tier_progress: float (0.0-100.0)  // % of requirements met for next tier
  fields_to_advance: string[]             // keys of unmet requirements
}
```

### Example Flow:
1. Org starts at INCOMPLETE
2. User fills in name, industry, state, employee_range → advances to BASIC
3. User adds 1 vendor, 1 domain, answers 1 security control → advances to ENHANCED
4. User selects revenue, compliance frameworks, data types, uploads file, answers 8+ controls → advances to COMPREHENSIVE

---

## Part 6: Form State Structure

Recommended TypeScript interface for form:

```typescript
interface AssessmentIntakeFormData {
  // Basic tier - required
  name: string;
  industry_label: string;
  primary_state: string;
  employee_range: string;
  
  // Enhanced tier - adds these
  security_controls: Record<string, "yes" | "no" | "unsure">;
  
  // Comprehensive tier - adds these
  revenue_range: string;
  compliance_frameworks: string[];
  data_types: string[];
  cloud_providers: string[];
  
  // Metadata for UI
  vendorCount: number;  // readonly - from API
  domainCount: number;  // readonly - from API
  uploadCount: number;  // readonly - from API
  controlsAnswered: number;  // computed from security_controls
}

interface AssessmentIntakeProgress {
  currentTier: "incomplete" | "basic" | "enhanced" | "comprehensive";
  nextTier: "basic" | "enhanced" | "comprehensive" | null;
  progressPercent: number;  // 0-100
  fieldsToAdvance: string[];  // keys blocking tier advancement
}
```

---

## Part 7: Frontend Form Flow Recommendations

### Step Grouping Strategy

**Step 1: Basic Information** (REQUIRED for BASIC tier)
- Company Name
- Industry
- State
- Employee Count

**Step 2: Financial Information** (OPTIONAL, needed for COMPREHENSIVE)
- Revenue Range
- Compliance Frameworks

**Step 3: Security Controls** (REQUIRED for ENHANCED, depth requirement for COMPREHENSIVE)
- 16 security controls grouped by category
- Each control has yes/no/unsure options
- Show progress: "X/8 controls needed for comprehensive tier"

**Step 4: Technology & Infrastructure** (OPTIONAL)
- Cloud Providers multi-select
- Data Types multi-select

**Step 5: Upload & Summary** (COMPREHENSIVE requirement)
- File upload widget
- Summary of selections
- Final submission

### Progress Indicators
- Show current tier at top
- Show next tier unlock requirements
- Color-code required vs optional sections
- Progress bar: "X/Y requirements met for next tier"

---

## Part 8: Key Implementation Notes

1. **Auto-save Strategy**: Save each form field to backend as user navigates (optimistic update)
2. **Validation**: Required fields enforced per tier, optional fields always allow skip
3. **Dependencies**: Vendor/domain/upload counts fetched from `/mine/intake` endpoint
4. **Error Handling**: If update fails, show toast/error message but don't block UI
5. **Draft State**: All updates are auto-saved, no explicit "save draft" needed
6. **Tier Progression**: Happens automatically on the backend after each org update

