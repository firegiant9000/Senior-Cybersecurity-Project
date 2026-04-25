import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import { createVendor } from "../api/vendors";
import "./OnboardingPage.css";

const INDUSTRY_OPTIONS = [
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

const EMPLOYEE_RANGES = [
  "1-10",
  "11-50",
  "51-200",
  "201-500",
  "501-1000",
  "1001+",
] as const;

const REVENUE_RANGES = [
  "Under $1M",
  "$1M-$5M",
  "$5M-$10M",
  "$10M-$50M",
  "$50M-$100M",
  "$100M+",
] as const;

const US_STATES = [
  { code: "AL", name: "Alabama" }, { code: "AK", name: "Alaska" },
  { code: "AZ", name: "Arizona" }, { code: "AR", name: "Arkansas" },
  { code: "CA", name: "California" }, { code: "CO", name: "Colorado" },
  { code: "CT", name: "Connecticut" }, { code: "DE", name: "Delaware" },
  { code: "FL", name: "Florida" }, { code: "GA", name: "Georgia" },
  { code: "HI", name: "Hawaii" }, { code: "ID", name: "Idaho" },
  { code: "IL", name: "Illinois" }, { code: "IN", name: "Indiana" },
  { code: "IA", name: "Iowa" }, { code: "KS", name: "Kansas" },
  { code: "KY", name: "Kentucky" }, { code: "LA", name: "Louisiana" },
  { code: "ME", name: "Maine" }, { code: "MD", name: "Maryland" },
  { code: "MA", name: "Massachusetts" }, { code: "MI", name: "Michigan" },
  { code: "MN", name: "Minnesota" }, { code: "MS", name: "Mississippi" },
  { code: "MO", name: "Missouri" }, { code: "MT", name: "Montana" },
  { code: "NE", name: "Nebraska" }, { code: "NV", name: "Nevada" },
  { code: "NH", name: "New Hampshire" }, { code: "NJ", name: "New Jersey" },
  { code: "NM", name: "New Mexico" }, { code: "NY", name: "New York" },
  { code: "NC", name: "North Carolina" }, { code: "ND", name: "North Dakota" },
  { code: "OH", name: "Ohio" }, { code: "OK", name: "Oklahoma" },
  { code: "OR", name: "Oregon" }, { code: "PA", name: "Pennsylvania" },
  { code: "RI", name: "Rhode Island" }, { code: "SC", name: "South Carolina" },
  { code: "SD", name: "South Dakota" }, { code: "TN", name: "Tennessee" },
  { code: "TX", name: "Texas" }, { code: "UT", name: "Utah" },
  { code: "VT", name: "Vermont" }, { code: "VA", name: "Virginia" },
  { code: "WA", name: "Washington" }, { code: "WV", name: "West Virginia" },
  { code: "WI", name: "Wisconsin" }, { code: "WY", name: "Wyoming" },
] as const;

const CLOUD_PROVIDERS = [
  "AWS", "Azure", "GCP", "Microsoft 365", "Google Workspace",
  "Salesforce", "Shopify", "QuickBooks", "Dropbox", "Slack", "Zoom",
] as const;

const COMPLIANCE_FRAMEWORKS = [
  "HIPAA", "PCI-DSS", "SOC 2", "CMMC", "NIST CSF", "ISO 27001", "None",
] as const;

const DATA_TYPES = [
  "PII (names, SSNs)",
  "PHI (health records)",
  "Payment card data",
  "Intellectual property",
  "Customer financial data",
  "None of these",
] as const;

const SECURITY_CONTROLS = [
  { key: "mfa_enabled", label: "MFA enabled for all users", category: "Identity & Access",
    hint: "Multi-Factor Authentication requires employees to verify their identity with a second step (e.g. a code texted to their phone) in addition to a password. e.g. Google Authenticator, Microsoft Authenticator, or SMS codes." },
  { key: "password_policy", label: "Password policy enforced", category: "Identity & Access",
    hint: "A written rule (enforced by your IT system) that requires passwords to meet minimum standards — e.g. at least 12 characters, no reuse of old passwords, and automatic lockout after failed attempts." },
  { key: "sso_in_use", label: "SSO in use", category: "Identity & Access",
    hint: "Single Sign-On lets employees log in once to access multiple apps (e.g. email, Slack, Salesforce) without separate passwords for each. e.g. Okta, Microsoft Entra ID (Azure AD), Google Workspace SSO." },
  { key: "edr_deployed", label: "EDR/antivirus deployed", category: "Endpoint Protection",
    hint: "Endpoint Detection & Response software monitors laptops and desktops for malicious activity and can automatically block or quarantine threats. e.g. CrowdStrike, SentinelOne, Microsoft Defender, or standard antivirus like Malwarebytes." },
  { key: "devices_encrypted", label: "Devices encrypted", category: "Endpoint Protection",
    hint: "Encryption scrambles the data on a device so it can't be read if stolen or lost. On Windows this is called BitLocker; on Mac it's FileVault. Answer Yes if this is turned on for company laptops and phones." },
  { key: "auto_patching", label: "Auto-patching enabled", category: "Endpoint Protection",
    hint: "Automatic patching means software updates (including security fixes) install themselves without requiring someone to manually approve each one. Unpatched software is one of the most common ways attackers get in." },
  { key: "email_filtering", label: "Email filtering / gateway", category: "Email Security",
    hint: "A service that scans incoming emails before they reach employees' inboxes, blocking spam, phishing attempts, and malicious attachments. e.g. Microsoft Defender for Office 365, Google Workspace spam filtering, Proofpoint, Mimecast." },
  { key: "phishing_training", label: "Phishing training conducted", category: "Email Security",
    hint: "Regular training that teaches employees how to spot fake emails designed to steal passwords or trick them into wiring money. Often includes simulated phishing tests. e.g. KnowBe4, Proofpoint Security Awareness." },
  { key: "firewall_in_place", label: "Firewall in place", category: "Network",
    hint: "A firewall acts as a gatekeeper between your internal network and the internet, blocking unauthorized traffic. Most business routers include a basic firewall; dedicated solutions offer stronger protection." },
  { key: "vpn_remote_access", label: "VPN for remote access", category: "Network",
    hint: "A Virtual Private Network creates an encrypted tunnel so remote employees connect to company resources securely — like having a private hallway over the public internet. e.g. Cisco AnyConnect, Palo Alto GlobalProtect, NordLayer." },
  { key: "network_segmentation", label: "Network segmentation", category: "Network",
    hint: "Dividing your network into separate zones so that if an attacker breaks into one area (e.g. guest Wi-Fi), they can't automatically reach sensitive systems (e.g. accounting or patient records). Common in healthcare and finance." },
  { key: "regular_backups", label: "Regular data backups", category: "Data Protection",
    hint: "Automatic, scheduled copies of your important files and systems stored somewhere separate (e.g. cloud storage or an offsite drive). Critical for recovering from ransomware attacks without paying a ransom." },
  { key: "backup_testing", label: "Backup restoration tested", category: "Data Protection",
    hint: "Having backups is only useful if they actually work when you need them. This means periodically doing a test restore to confirm you can recover your data. Many businesses discover their backups were broken only after a disaster." },
  { key: "data_classification", label: "Data classification policy", category: "Data Protection",
    hint: "A written policy that labels data by sensitivity level (e.g. Public, Internal, Confidential, Restricted) and specifies how each level must be stored, shared, and deleted. Helps employees know what data needs extra protection." },
  { key: "ir_plan_documented", label: "IR plan documented", category: "Incident Response",
    hint: "An Incident Response plan is a written playbook for what your team does when a cyberattack or data breach occurs — who to call, what to shut down, how to notify customers. Having one reduces chaos and recovery time." },
  { key: "ir_plan_tested", label: "IR plan tested within 12 months", category: "Incident Response",
    hint: "A tabletop exercise or drill where your team walks through a simulated attack scenario to practice the IR plan. Testing reveals gaps before a real incident. Regulators like HIPAA and PCI-DSS often require this." },
] as const;

const TOTAL_STEPS = 9;

interface CloudVendor {
  name: string;
  product: string;
}

interface FormData {
  name: string;
  industry_label: string;
  primary_state: string;
  employee_range: string;
  revenue_range: string;
  security_controls: Record<string, "yes" | "no" | "unsure">;
  cloud_vendors: CloudVendor[];
  compliance_frameworks: string[];
  data_types: string[];
}

export default function OnboardingPage({ onComplete }: { onComplete: () => void }) {
  const navigate = useNavigate();
  const { orgId, logout } = useAuth();

  // Redirect users who already have an org back to dashboard
  useEffect(() => {
    if (orgId !== null) navigate("/", { replace: true });
  }, [orgId, navigate]);

  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState<FormData>({
    name: "",
    industry_label: "",
    primary_state: "",
    employee_range: "",
    revenue_range: "",
    security_controls: {},
    cloud_vendors: [],
    compliance_frameworks: [],
    data_types: [],
  });

  const update = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setError("");
  };

  const toggleListItem = (field: "compliance_frameworks" | "data_types", value: string) => {
    setForm((prev) => {
      const current = prev[field] as string[];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...prev, [field]: next };
    });
  };

  const toggleVendor = (name: string) => {
    setForm((prev) => {
      const exists = prev.cloud_vendors.some((v) => v.name === name);
      return {
        ...prev,
        cloud_vendors: exists
          ? prev.cloud_vendors.filter((v) => v.name !== name)
          : [...prev.cloud_vendors, { name, product: "" }],
      };
    });
  };

  const setVendorProduct = (name: string, product: string) => {
    setForm((prev) => ({
      ...prev,
      cloud_vendors: prev.cloud_vendors.map((v) =>
        v.name === name ? { ...v, product } : v,
      ),
    }));
  };

  const setControlValue = (key: string, value: "yes" | "no" | "unsure") => {
    setForm((prev) => ({
      ...prev,
      security_controls: { ...prev.security_controls, [key]: value },
    }));
  };

  const canAdvance = (): boolean => {
    switch (step) {
      case 1: return form.name.trim().length >= 1;
      case 2: return form.industry_label !== "";
      case 3: return form.primary_state !== "";
      case 4: return form.employee_range !== "";
      case 5: return true; // revenue is optional
      case 6: return true; // security controls optional
      case 7: return true; // cloud providers optional
      case 8: return true; // compliance optional
      case 9: return true; // data types optional
      default: return false;
    }
  };

  const handleNext = () => {
    if (!canAdvance()) return;
    if (step < TOTAL_STEPS) {
      setStep(step + 1);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");

    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      industry_label: form.industry_label,
      primary_state: form.primary_state,
      employee_range: form.employee_range,
      revenue_range: form.revenue_range || "",
      security_controls: Object.keys(form.security_controls).length > 0 ? form.security_controls : null,
      cloud_providers: form.cloud_vendors.length > 0 ? form.cloud_vendors.map((v) => v.name) : null,
      compliance_frameworks: form.compliance_frameworks.length > 0 ? form.compliance_frameworks : null,
      data_types: form.data_types.length > 0 ? form.data_types : null,
    };

    try {
      const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/onboarding/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? "Failed to create organization");
      }

      const created = await resp.json().catch(() => null) as { id?: number } | null;
      if (created?.id && form.cloud_vendors.length > 0) {
        await Promise.allSettled(
          form.cloud_vendors.map((v) => createVendor(created.id as number, v.name, v.product)),
        );
      }

      onComplete();
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  const renderStep = () => {
    switch (step) {
      case 1:
        return (
          <div className="onboarding-step">
            <h2>What's your company name?</h2>
            <p className="step-description">This helps us personalize your threat intelligence dashboard.</p>
            <div className="onboarding-form-group">
              <label htmlFor="company-name">Company Name</label>
              <input
                id="company-name"
                type="text"
                value={form.name}
                onChange={(e) => update("name", e.target.value)}
                placeholder="Acme Corp"
                maxLength={255}
                autoFocus
              />
            </div>
          </div>
        );
      case 2:
        return (
          <div className="onboarding-step">
            <h2>What industry are you in?</h2>
            <p className="step-description">We'll tailor threat data to your sector's risk profile.</p>
            <div className="onboarding-form-group">
              <label htmlFor="industry">Industry</label>
              <select
                id="industry"
                value={form.industry_label}
                onChange={(e) => update("industry_label", e.target.value)}
              >
                <option value="" disabled>Select your industry</option>
                {INDUSTRY_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          </div>
        );
      case 3:
        return (
          <div className="onboarding-step">
            <h2>Where is your company based?</h2>
            <p className="step-description">State-level data helps us show regional threat trends.</p>
            <div className="onboarding-form-group">
              <label htmlFor="state">State</label>
              <select
                id="state"
                value={form.primary_state}
                onChange={(e) => update("primary_state", e.target.value)}
              >
                <option value="" disabled>Select your state</option>
                {US_STATES.map((s) => (
                  <option key={s.code} value={s.code}>{s.name}</option>
                ))}
              </select>
            </div>
          </div>
        );
      case 4:
        return (
          <div className="onboarding-step">
            <h2>How large is your company?</h2>
            <p className="step-description">Company size helps us calibrate risk scoring.</p>
            <div className="onboarding-form-group">
              <label htmlFor="employees">Number of Employees</label>
              <select
                id="employees"
                value={form.employee_range}
                onChange={(e) => update("employee_range", e.target.value)}
              >
                <option value="" disabled>Select company size</option>
                {EMPLOYEE_RANGES.map((opt) => (
                  <option key={opt} value={opt}>{opt} employees</option>
                ))}
              </select>
            </div>
          </div>
        );
      case 5:
        return (
          <div className="onboarding-step">
            <h2>What's your annual revenue?</h2>
            <p className="step-description">This is optional and helps refine economic impact analysis.</p>
            <div className="onboarding-form-group">
              <label htmlFor="revenue">Annual Revenue (optional)</label>
              <select
                id="revenue"
                value={form.revenue_range}
                onChange={(e) => update("revenue_range", e.target.value)}
              >
                <option value="">Prefer not to say</option>
                {REVENUE_RANGES.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          </div>
        );
      case 6: {
        const categories = [...new Set(SECURITY_CONTROLS.map((c) => c.category))];
        return (
          <div className="onboarding-step">
            <h2>Security Controls</h2>
            <p className="step-description">
              Tell us which security controls are in place. This enables CIS IG1 baseline scoring.
              You can update these later in Organization Profile.
            </p>
            {categories.map((cat) => (
              <div key={cat} className="onboarding-control-group">
                <h3 className="control-category">{cat}</h3>
                {SECURITY_CONTROLS.filter((c) => c.category === cat).map((control) => {
                  const val = form.security_controls[control.key] ?? "unsure";
                  return (
                    <div key={control.key} className="onboarding-control-row">
                      <div className="control-label-group">
                        <span className="control-label">{control.label}</span>
                        <span className="control-hint">{control.hint}</span>
                      </div>
                      <div className="control-toggle">
                        {(["yes", "no", "unsure"] as const).map((opt) => (
                          <button
                            key={opt}
                            type="button"
                            className={`control-option${val === opt ? " selected" : ""}`}
                            onClick={() => setControlValue(control.key, opt)}
                          >
                            {opt === "yes" ? "Yes" : opt === "no" ? "No" : "Unsure"}
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        );
      }
      case 7:
        return (
          <div className="onboarding-step">
            <h2>Cloud & SaaS Providers</h2>
            <p className="step-description">
              Select cloud platforms and SaaS tools your organization uses. This helps match CVEs to your stack.
            </p>
            <div className="onboarding-vendor-list">
              {CLOUD_PROVIDERS.map((provider) => {
                const entry = form.cloud_vendors.find((v) => v.name === provider);
                const checked = !!entry;
                return (
                  <div key={provider} className={`onboarding-vendor-row${checked ? " selected" : ""}`}>
                    <label className="onboarding-vendor-check">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleVendor(provider)}
                      />
                      <span className="onboarding-vendor-name">{provider}</span>
                    </label>
                    {checked && (
                      <input
                        type="text"
                        className="onboarding-vendor-product"
                        placeholder="Product / plan (optional)"
                        value={entry?.product ?? ""}
                        onChange={(e) => setVendorProduct(provider, e.target.value)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      case 8:
        return (
          <div className="onboarding-step">
            <h2>Compliance Frameworks</h2>
            <p className="step-description">
              Which compliance frameworks does your organization track? We'll flag gaps based on your industry and data.
            </p>
            <div className="onboarding-checklist">
              {COMPLIANCE_FRAMEWORKS.map((fw) => (
                <label key={fw} className="onboarding-check-item">
                  <input
                    type="checkbox"
                    checked={form.compliance_frameworks.includes(fw)}
                    onChange={() => toggleListItem("compliance_frameworks", fw)}
                  />
                  {fw}
                </label>
              ))}
            </div>
          </div>
        );
      case 9:
        return (
          <div className="onboarding-step">
            <h2>Data Types Handled</h2>
            <p className="step-description">
              What kinds of sensitive data does your organization handle? This drives regulatory exposure analysis.
            </p>
            <div className="onboarding-checklist">
              {DATA_TYPES.map((dt) => (
                <label key={dt} className="onboarding-check-item">
                  <input
                    type="checkbox"
                    checked={form.data_types.includes(dt)}
                    onChange={() => toggleListItem("data_types", dt)}
                  />
                  {dt}
                </label>
              ))}
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div className="onboarding-page">
      <div className="onboarding-card">
        <div className="onboarding-header">
          <h1>Set Up Your Organization</h1>
          <p>Step {step} of {TOTAL_STEPS}</p>
          <button type="button" className="onboarding-logout-btn" onClick={handleLogout}>
            Sign out
          </button>
        </div>

        <div className="onboarding-progress">
          {Array.from({ length: TOTAL_STEPS }, (_, i) => (
            <div
              key={i}
              className={`onboarding-progress-step${
                i + 1 < step ? " completed" : i + 1 === step ? " active" : ""
              }`}
            />
          ))}
        </div>

        {error && <div className="onboarding-error">{error}</div>}

        {renderStep()}

        <div className="onboarding-actions">
          {step > 1 && (
            <button
              type="button"
              className="onboarding-btn secondary"
              onClick={handleBack}
              disabled={submitting}
            >
              Back
            </button>
          )}
          <button
            type="button"
            className="onboarding-btn"
            onClick={handleNext}
            disabled={!canAdvance() || submitting}
          >
            {submitting ? "Creating..." : step === TOTAL_STEPS ? "Complete Setup" : "Continue"}
          </button>
        </div>

        {step >= 5 && step < TOTAL_STEPS && (
          <button
            type="button"
            className="onboarding-skip-btn"
            onClick={handleSubmit}
            disabled={submitting}
          >
            Skip remaining and finish
          </button>
        )}
      </div>
    </div>
  );
}
