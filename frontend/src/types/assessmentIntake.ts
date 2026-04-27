/**
 * TypeScript types for the Assessment Intake Wizard form.
 */

export interface AssessmentIntakeFormData {
  // BASIC tier - required
  name: string;
  industry_label: string;
  primary_state: string;
  employee_range: string;
  primary_domain: string;
  primary_vendor: string;

  // ENHANCED tier additions
  security_controls: Record<string, "yes" | "no" | "unsure">;

  // COMPREHENSIVE tier additions
  revenue_range: string;
  compliance_frameworks: string[];
  data_types: string[];
  cloud_providers: string[];
}

export interface AssessmentIntakeStepConfig {
  stepNumber: number;
  title: string;
  description: string;
  fields: string[]; // field keys that belong to this step
  requiredTier: "basic" | "enhanced" | "comprehensive";
  isRequired: boolean; // whether all fields in step are required to advance
}

export const INDUSTRY_OPTIONS = [
  "Finance & Insurance",
  "Healthcare",
  "Tech & Software",
  "Government",
  "Retail & E-Commerce",
  "Education",
  "Manufacturing",
  "Professional Services",
  "Real Estate",
  "Construction",
  "Legal Services",
  "Transportation",
  "Hospitality",
  "Non-Profit",
  "Other",
] as const;

export const EMPLOYEE_RANGES = [
  "1-10",
  "11-50",
  "51-200",
  "201-500",
  "501-1000",
  "1001+",
] as const;

export const REVENUE_RANGES = [
  "Under $1M",
  "$1M-$5M",
  "$5M-$10M",
  "$10M-$50M",
  "$50M-$100M",
  "$100M+",
] as const;

export const US_STATES = [
  { code: "AL", name: "Alabama" },
  { code: "AK", name: "Alaska" },
  { code: "AZ", name: "Arizona" },
  { code: "AR", name: "Arkansas" },
  { code: "CA", name: "California" },
  { code: "CO", name: "Colorado" },
  { code: "CT", name: "Connecticut" },
  { code: "DE", name: "Delaware" },
  { code: "FL", name: "Florida" },
  { code: "GA", name: "Georgia" },
  { code: "HI", name: "Hawaii" },
  { code: "ID", name: "Idaho" },
  { code: "IL", name: "Illinois" },
  { code: "IN", name: "Indiana" },
  { code: "IA", name: "Iowa" },
  { code: "KS", name: "Kansas" },
  { code: "KY", name: "Kentucky" },
  { code: "LA", name: "Louisiana" },
  { code: "ME", name: "Maine" },
  { code: "MD", name: "Maryland" },
  { code: "MA", name: "Massachusetts" },
  { code: "MI", name: "Michigan" },
  { code: "MN", name: "Minnesota" },
  { code: "MS", name: "Mississippi" },
  { code: "MO", name: "Missouri" },
  { code: "MT", name: "Montana" },
  { code: "NE", name: "Nebraska" },
  { code: "NV", name: "Nevada" },
  { code: "NH", name: "New Hampshire" },
  { code: "NJ", name: "New Jersey" },
  { code: "NM", name: "New Mexico" },
  { code: "NY", name: "New York" },
  { code: "NC", name: "North Carolina" },
  { code: "ND", name: "North Dakota" },
  { code: "OH", name: "Ohio" },
  { code: "OK", name: "Oklahoma" },
  { code: "OR", name: "Oregon" },
  { code: "PA", name: "Pennsylvania" },
  { code: "RI", name: "Rhode Island" },
  { code: "SC", name: "South Carolina" },
  { code: "SD", name: "South Dakota" },
  { code: "TN", name: "Tennessee" },
  { code: "TX", name: "Texas" },
  { code: "UT", name: "Utah" },
  { code: "VT", name: "Vermont" },
  { code: "VA", name: "Virginia" },
  { code: "WA", name: "Washington" },
  { code: "WV", name: "West Virginia" },
  { code: "WI", name: "Wisconsin" },
  { code: "WY", name: "Wyoming" },
] as const;

export const COMPLIANCE_FRAMEWORKS = [
  "HIPAA",
  "PCI-DSS",
  "SOC 2",
  "CMMC",
  "NIST CSF",
  "ISO 27001",
  "None",
  "Unsure",
] as const;

// Mutually exclusive framework choices: selecting one of these clears the
// substantive frameworks (and vice versa).
export const COMPLIANCE_FRAMEWORK_EXCLUSIVE = ["None", "Unsure"] as const;

export const DOMAIN_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/i;

export const DATA_TYPES = [
  "PII (names, SSNs)",
  "PHI (health records)",
  "Payment card data",
  "Intellectual property",
  "Customer financial data",
  "None of these",
] as const;

export const CLOUD_PROVIDERS = [
  "AWS",
  "Azure",
  "GCP",
  "Microsoft 365",
  "Google Workspace",
  "Salesforce",
  "Shopify",
  "QuickBooks",
  "Dropbox",
  "Slack",
  "Zoom",
] as const;

export interface SecurityControl {
  key: string;
  label: string;
  category: string;
  hint: string;
}

export const SECURITY_CONTROLS: SecurityControl[] = [
  {
    key: "mfa_enabled",
    label: "MFA enabled for all users",
    category: "Identity & Access",
    hint: "Multi-Factor Authentication requires employees to verify their identity with a second step (e.g. a code texted to their phone) in addition to a password. e.g. Google Authenticator, Microsoft Authenticator, or SMS codes.",
  },
  {
    key: "password_policy",
    label: "Password policy enforced",
    category: "Identity & Access",
    hint: "A written rule (enforced by your IT system) that requires passwords to meet minimum standards — e.g. at least 12 characters, no reuse of old passwords, and automatic lockout after failed attempts.",
  },
  {
    key: "sso_in_use",
    label: "SSO in use",
    category: "Identity & Access",
    hint: "Single Sign-On lets employees log in once to access multiple apps (e.g. email, Slack, Salesforce) without separate passwords for each. e.g. Okta, Microsoft Entra ID (Azure AD), Google Workspace SSO.",
  },
  {
    key: "edr_deployed",
    label: "EDR/antivirus deployed",
    category: "Endpoint Protection",
    hint: "Endpoint Detection & Response software monitors laptops and desktops for malicious activity and can automatically block or quarantine threats. e.g. CrowdStrike, SentinelOne, Microsoft Defender, or standard antivirus like Malwarebytes.",
  },
  {
    key: "devices_encrypted",
    label: "Devices encrypted",
    category: "Endpoint Protection",
    hint: "Encryption scrambles the data on a device so it can't be read if stolen or lost. On Windows this is called BitLocker; on Mac it's FileVault. Answer Yes if this is turned on for company laptops and phones.",
  },
  {
    key: "auto_patching",
    label: "Auto-patching enabled",
    category: "Endpoint Protection",
    hint: "Automatic patching means software updates (including security fixes) install themselves without requiring someone to manually approve each one. Unpatched software is one of the most common ways attackers get in.",
  },
  {
    key: "email_filtering",
    label: "Email filtering / gateway",
    category: "Email Security",
    hint: "A service that scans incoming emails before they reach employees' inboxes, blocking spam, phishing attempts, and malicious attachments. e.g. Microsoft Defender for Office 365, Google Workspace spam filtering, Proofpoint, Mimecast.",
  },
  {
    key: "phishing_training",
    label: "Phishing training conducted",
    category: "Email Security",
    hint: "Regular training that teaches employees how to spot fake emails designed to steal passwords or trick them into wiring money. Often includes simulated phishing tests. e.g. KnowBe4, Proofpoint Security Awareness.",
  },
  {
    key: "firewall_in_place",
    label: "Firewall in place",
    category: "Network",
    hint: "A firewall acts as a gatekeeper between your internal network and the internet, blocking unauthorized traffic. Most business routers include a basic firewall; dedicated solutions offer stronger protection.",
  },
  {
    key: "vpn_remote_access",
    label: "VPN for remote access",
    category: "Network",
    hint: "A Virtual Private Network creates an encrypted tunnel so remote employees connect to company resources securely — like having a private hallway over the public internet. e.g. Cisco AnyConnect, Palo Alto GlobalProtect, NordLayer.",
  },
  {
    key: "network_segmentation",
    label: "Network segmentation",
    category: "Network",
    hint: "Dividing your network into separate zones so that if an attacker breaks into one area (e.g. guest Wi-Fi), they can't automatically reach sensitive systems (e.g. accounting or patient records). Common in healthcare and finance.",
  },
  {
    key: "regular_backups",
    label: "Regular data backups",
    category: "Data Protection",
    hint: "Automatic, scheduled copies of your important files and systems stored somewhere separate (e.g. cloud storage or an offsite drive). Critical for recovering from ransomware attacks without paying a ransom.",
  },
  {
    key: "backup_testing",
    label: "Backup restoration tested",
    category: "Data Protection",
    hint: "Having backups is only useful if they actually work when you need them. This means periodically doing a test restore to confirm you can recover your data. Many businesses discover their backups were broken only after a disaster.",
  },
  {
    key: "data_classification",
    label: "Data classification policy",
    category: "Data Protection",
    hint: "A written policy that labels data by sensitivity level (e.g. Public, Internal, Confidential, Restricted) and specifies how each level must be stored, shared, and deleted. Helps employees know what data needs extra protection.",
  },
  {
    key: "ir_plan_documented",
    label: "IR plan documented",
    category: "Incident Response",
    hint: "An Incident Response plan is a written playbook for what your team does when a cyberattack or data breach occurs — who to call, what to shut down, how to notify customers. Having one reduces chaos and recovery time.",
  },
  {
    key: "ir_plan_tested",
    label: "IR plan tested within 12 months",
    category: "Incident Response",
    hint: "A tabletop exercise or drill where your team walks through a simulated attack scenario to practice the IR plan. Testing reveals gaps before a real incident. Regulators like HIPAA and PCI-DSS often require this.",
  },
];
