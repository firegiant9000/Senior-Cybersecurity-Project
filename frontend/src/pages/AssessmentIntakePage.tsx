import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useAssessmentIntake } from "../hooks/useAssessmentIntake";
import { useIntakePreview } from "../hooks/useIntakePreview";
import { fetchWithAuth, API_BASE_URL } from "../api/fetchWithAuth";
import StepIndicator from "../components/shared/StepIndicator";
import FormSection from "../components/shared/FormSection";
import ProgressSummary from "../components/shared/ProgressSummary";
import IntakeProgressIndicator from "../components/shared/IntakeProgressIndicator";
import RequiredBadge from "../components/shared/RequiredBadge";
import {
  type AssessmentIntakeFormData,
  INDUSTRY_OPTIONS,
  EMPLOYEE_RANGES,
  REVENUE_RANGES,
  US_STATES,
  COMPLIANCE_FRAMEWORKS,
  COMPLIANCE_FRAMEWORK_EXCLUSIVE,
  DATA_TYPES,
  CLOUD_PROVIDERS,
  SECURITY_CONTROLS,
  DOMAIN_PATTERN,
} from "../types/assessmentIntake";
import { createVendor, listVendors } from "../api/vendors";
import { addDomain, listDomains } from "../api/domains";
import "./AssessmentIntakePage.css";

const TOTAL_STEPS = 5;

const STEPS = [
  {
    title: "Company Basics",
    optional: false,
    description: "Required for risk assessment baseline",
  },
  {
    title: "Financial & Compliance",
    optional: true,
    description: "Optional: improves accuracy",
  },
  {
    title: "Security Controls",
    optional: false,
    description: "Enables detailed control assessment",
  },
  {
    title: "Technology & Infrastructure",
    optional: true,
    description: "Optional: cloud and data details",
  },
  {
    title: "Review & Confirm",
    optional: false,
    description: "Summary of your intake",
  },
];

export default function AssessmentIntakePage() {
  const navigate = useNavigate();
  const { user, orgId, refreshProfile } = useAuth();
  const { data: intakeData, loading: intakeLoading, refresh: refreshIntake } = useAssessmentIntake();

  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Tracks the in-flight Next click so we can (a) show a spinner and
  // (b) disable the button to prevent the "have to click twice" issue
  // where a fast user clicks again before the create-org POST resolves.
  const [advancing, setAdvancing] = useState(false);
  const vendorSyncedRef = useRef<string>("");
  const domainSyncedRef = useRef<string>("");
  // Default every security control to "unsure" so the UI's default highlight
  // and the persisted state agree. Without this, controls the user never
  // touches stay absent from state and the tier check counts them as
  // unanswered even though the form looks fully filled in.
  const defaultSecurityControls = (): Record<string, "yes" | "no" | "unsure"> =>
    Object.fromEntries(SECURITY_CONTROLS.map((c) => [c.key, "unsure" as const]));

  const [form, setForm] = useState<AssessmentIntakeFormData>({
    name: "",
    industry_label: "",
    primary_state: "",
    employee_range: "",
    primary_domain: "",
    primary_vendor: "",
    primary_product: "",
    revenue_range: "",
    security_controls: defaultSecurityControls(),
    compliance_frameworks: [],
    data_types: [],
    cloud_providers: [],
  });

  // The tier preview on step 5 reflects whatever the backend has. Re-fetch
  // when the user lands on it so the saves they just made show up.
  useEffect(() => {
    if (step === 5) refreshIntake();
  }, [step, refreshIntake]);

  // Load existing org data
  useEffect(() => {
    const loadOrgData = async () => {
      if (!orgId) return;
      try {
        const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/organizations/${orgId}`, {
          method: "GET",
        });
        if (resp.ok) {
          const org = await resp.json();
          setForm((prev) => ({
            ...prev,
            name: org.name || "",
            industry_label: org.industry_label || "",
            primary_state: org.primary_state || "",
            employee_range: org.employee_range || "",
            primary_domain: org.primary_domain || "",
            primary_vendor: prev.primary_vendor,
            primary_product: prev.primary_product,
            revenue_range: org.revenue_range || "",
            // Merge so any control the backend doesn't have yet falls back
            // to the "unsure" default rather than dropping out of state.
            security_controls: { ...defaultSecurityControls(), ...(org.security_controls || {}) },
            compliance_frameworks: org.compliance_frameworks || [],
            data_types: org.data_types || [],
            cloud_providers: org.cloud_providers || [],
          }));
        }
      } catch (err) {
        console.error("Failed to load org data:", err);
      }

      // Pre-seed the sync refs from existing rows so we don't POST duplicates
      // (and pop a 409 in the network tab) on a returning user's wizard run.
      try {
        const [domainList, vendorList] = await Promise.all([
          listDomains(orgId, 1, 100),
          listVendors(orgId, 1, 100),
        ]);
        const domains = new Set(
          (domainList.items || []).map((d) => d.domain_name.toLowerCase()),
        );
        const vendors = new Set(
          (vendorList.items || []).map((v) => v.vendor_name.toLowerCase()),
        );
        // Mark any matching primary_* as already synced.
        // (Match against current form state via setForm so we don't race the
        // org GET above.)
        setForm((prev) => {
          if (prev.primary_domain && domains.has(prev.primary_domain.trim().toLowerCase())) {
            domainSyncedRef.current = prev.primary_domain.trim();
          }
          if (prev.primary_vendor && vendors.has(prev.primary_vendor.trim().toLowerCase())) {
            vendorSyncedRef.current = prev.primary_vendor.trim();
          }
          return prev;
        });
      } catch (err) {
        // Non-fatal — worst case we'll still try to POST and swallow the 409.
        console.warn("Failed to pre-seed vendor/domain sync refs:", err);
      }
    };

    if (user && orgId) {
      loadOrgData();
    }
  }, [user, orgId]);

  // Live tier preview: send the in-progress form to the backend (debounced) so
  // the sidebar reflects "what tier would I have right now if I submitted?".
  // The security_controls payload mirrors what handleNext's PUT would send so
  // the preview's tier evaluation matches the post-submit evaluation exactly —
  // any divergence here would surface as a misleading "unlocked" toast that
  // disappears the moment the user advances.
  const previewPayload = useMemo(() => {
    return {
      name: form.name.trim() || null,
      industry_label: form.industry_label || null,
      primary_state: form.primary_state || null,
      employee_range: form.employee_range || null,
      revenue_range: form.revenue_range || null,
      primary_domain: form.primary_domain.trim() || null,
      primary_vendor: form.primary_vendor.trim() || null,
      security_controls:
        Object.keys(form.security_controls).length > 0 ? form.security_controls : null,
      compliance_frameworks:
        form.compliance_frameworks.length > 0 ? form.compliance_frameworks : null,
      data_types: form.data_types.length > 0 ? form.data_types : null,
    };
  }, [form]);

  const { preview, loading: previewLoading } = useIntakePreview(
    previewPayload,
    Boolean(user) && step < 5,
  );

  const updateField = (field: keyof AssessmentIntakeFormData, value: unknown) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setError("");
  };

  const toggleListItem = (
    field: "compliance_frameworks" | "data_types" | "cloud_providers",
    value: string
  ) => {
    setForm((prev) => {
      const current = prev[field] as string[];
      const isOn = current.includes(value);
      let next = isOn ? current.filter((v) => v !== value) : [...current, value];

      if (field === "compliance_frameworks" && !isOn) {
        const exclusives = COMPLIANCE_FRAMEWORK_EXCLUSIVE as readonly string[];
        if (exclusives.includes(value)) {
          // Selecting "None" or "Unsure" clears all other choices.
          next = [value];
        } else {
          // Selecting a substantive framework clears the exclusive options.
          next = next.filter((v) => !exclusives.includes(v));
        }
      }
      return { ...prev, [field]: next };
    });
  };

  const domainIsValid = (value: string): boolean => {
    const trimmed = value.trim();
    return trimmed === "" || DOMAIN_PATTERN.test(trimmed);
  };

  const setControlValue = (key: string, value: "yes" | "no" | "unsure") => {
    setForm((prev) => ({
      ...prev,
      security_controls: { ...prev.security_controls, [key]: value },
    }));
  };

  const canAdvanceFromStep = (): boolean => {
    switch (step) {
      case 1:
        return (
          form.name.trim().length > 0 &&
          form.industry_label !== "" &&
          form.primary_state !== "" &&
          form.employee_range !== "" &&
          domainIsValid(form.primary_domain)
        );
      case 2:
        return true; // financial & compliance optional
      case 3:
        return Object.keys(form.security_controls).length > 0;
      case 4:
        return true; // cloud & data optional
      case 5:
        return true; // review step
      default:
        return false;
    }
  };

  const buildPayload = () => ({
    name: form.name.trim(),
    industry_label: form.industry_label,
    primary_state: form.primary_state,
    employee_range: form.employee_range,
    primary_domain: form.primary_domain.trim() || null,
    revenue_range: form.revenue_range || null,
    security_controls:
      Object.keys(form.security_controls).length > 0 ? form.security_controls : null,
    compliance_frameworks:
      form.compliance_frameworks.length > 0 ? form.compliance_frameworks : null,
    data_types: form.data_types.length > 0 ? form.data_types : null,
    cloud_providers: form.cloud_providers.length > 0 ? form.cloud_providers : null,
  });

  const createOrg = async (): Promise<void> => {
    const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/onboarding/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(
        (body as { detail?: string }).detail ?? "Failed to create organization",
      );
    }
    await refreshProfile();
  };

  // Vendor and domain are stored in their own tables (the tier preview counts
  // those rows, not the form fields), so push them as soon as we have an orgId.
  const syncVendorAndDomain = async (targetOrgId: number): Promise<void> => {
    const vendorName = form.primary_vendor.trim();
    const productName = form.primary_product.trim();
    // Track vendor+product as a single sync key so editing the product
    // alone re-pushes (the unique constraint covers both columns).
    const vendorSyncKey = productName ? `${vendorName}::${productName}` : vendorName;
    if (vendorName && vendorSyncedRef.current !== vendorSyncKey) {
      try {
        // idempotent=true so re-runs of the wizard don't 409 on the same vendor.
        await createVendor(targetOrgId, vendorName, productName, { idempotent: true });
      } catch (vendorErr) {
        console.warn("Failed to add primary vendor:", vendorErr);
      } finally {
        vendorSyncedRef.current = vendorSyncKey;
      }
    }
    const domainName = form.primary_domain.trim();
    if (domainName && domainSyncedRef.current !== domainName) {
      try {
        await addDomain(targetOrgId, domainName);
      } catch (domainErr) {
        // Duplicate (409) just means the row already exists from a prior run -
        // benign for the wizard, so swallow it without a console warning.
        const msg = domainErr instanceof Error ? domainErr.message : "";
        if (!/already exists/i.test(msg)) {
          console.warn("Failed to add primary domain:", domainErr);
        }
      } finally {
        // Either way, don't retry this domain again in the same session.
        domainSyncedRef.current = domainName;
      }
    }
  };

  const handleNext = async () => {
    if (advancing || submitting) return; // Re-entrancy guard.
    if (!canAdvanceFromStep()) {
      setError("Please fill in all required fields");
      return;
    }
    setError("");
    setAdvancing(true);

    try {
      // Save form on each step
      if (step < TOTAL_STEPS) {
        let effectiveOrgId = orgId;
        try {
          if (!orgId) {
            await createOrg();
            // refreshProfile() updates the auth context but our closure still
            // sees the old null orgId until the next render. Read it back from
            // /auth/me so we can sync vendor/domain right away.
            const meResp = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
            if (meResp.ok) {
              const me = await meResp.json();
              effectiveOrgId = me.org_id ?? null;
            }
          } else {
            const resp = await fetchWithAuth(
              `${API_BASE_URL}/api/v1/organizations/${orgId}`,
              {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(buildPayload()),
              },
            );
            if (!resp.ok) {
              const body = await resp.json().catch(() => ({}));
              throw new Error(
                (body as { detail?: string }).detail ?? `Save failed (${resp.status})`,
              );
            }
          }
        } catch (err) {
          if (!orgId) {
            // Org creation must succeed before we can advance — surface the error.
            setError(err instanceof Error ? err.message : "Failed to create organization");
            return;
          }
          // Surface PUT failures so we don't silently lose user input.
          setError(err instanceof Error ? err.message : "Failed to save");
          return;
        }
        if (effectiveOrgId) {
          await syncVendorAndDomain(effectiveOrgId);
        }
        setStep(step + 1);
      } else {
        await handleSubmit();
      }
    } finally {
      setAdvancing(false);
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");

    try {
      if (!orgId) {
        await createOrg();
      } else {
        const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/organizations/${orgId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildPayload()),
        });
        if (!resp.ok) {
          const body = await resp.json().catch(() => ({}));
          throw new Error(
            (body as { detail?: string }).detail ?? "Failed to save assessment",
          );
        }
      }

      // Final pass to catch anything skipped (e.g. user edited domain on step 5).
      if (orgId) await syncVendorAndDomain(orgId);

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
          <div className="intake-step-content">
            <FormSection
              title="Company Information"
              description="Enter basic details about your organization"
              required
            >
              <div className="intake-form-group">
                <label htmlFor="name">
                  Company Name
                  <RequiredBadge required />
                </label>
                <input
                  id="name"
                  type="text"
                  value={form.name}
                  onChange={(e) => updateField("name", e.target.value)}
                  placeholder="Acme Corporation"
                  maxLength={255}
                  autoFocus
                />
              </div>

              <div className="intake-form-group">
                <label htmlFor="industry">
                  Industry
                  <RequiredBadge required />
                </label>
                <select
                  id="industry"
                  value={form.industry_label}
                  onChange={(e) => updateField("industry_label", e.target.value)}
                >
                  <option value="">Select your industry</option>
                  {INDUSTRY_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>

              <div className="intake-form-group">
                <label htmlFor="state">
                  Primary State
                  <RequiredBadge required />
                </label>
                <select
                  id="state"
                  value={form.primary_state}
                  onChange={(e) => updateField("primary_state", e.target.value)}
                >
                  <option value="">Select your state</option>
                  {US_STATES.map((s) => (
                    <option key={s.code} value={s.code}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="intake-form-group">
                <label htmlFor="employees">
                  Number of Employees
                  <RequiredBadge required />
                </label>
                <select
                  id="employees"
                  value={form.employee_range}
                  onChange={(e) => updateField("employee_range", e.target.value)}
                >
                  <option value="">Select company size</option>
                  {EMPLOYEE_RANGES.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt} employees
                    </option>
                  ))}
                </select>
              </div>

              <div className="intake-form-group">
                <label htmlFor="primary_domain">
                  Primary Domain
                  <RequiredBadge optional />
                </label>
                <p className="intake-field-hint">
                  Used for domain-based threat exposure checks (DNS, SSL, breach data).
                </p>
                <input
                  id="primary_domain"
                  type="text"
                  value={form.primary_domain}
                  onChange={(e) => updateField("primary_domain", e.target.value)}
                  placeholder="acme.com"
                  maxLength={255}
                  autoComplete="off"
                />
                {form.primary_domain.trim() !== "" &&
                  !domainIsValid(form.primary_domain) && (
                    <p className="intake-field-error">
                      Enter a valid domain (e.g. acme.com).
                    </p>
                  )}
              </div>

              <div className="intake-form-group">
                <label htmlFor="primary_vendor">
                  Primary Vendor
                  <RequiredBadge optional />
                </label>
                <p className="intake-field-hint">
                  Your most important software vendor. We'll seed your vendor stack
                  so you immediately see relevant alerts. You can add more later.
                </p>
                <input
                  id="primary_vendor"
                  type="text"
                  value={form.primary_vendor}
                  onChange={(e) => updateField("primary_vendor", e.target.value)}
                  placeholder="Microsoft, Cisco, Atlassian…"
                  maxLength={255}
                  autoComplete="off"
                />
              </div>

              <div className="intake-form-group">
                <label htmlFor="primary_product">
                  Primary Product
                  <RequiredBadge optional />
                </label>
                <p className="intake-field-hint">
                  Optional, but recommended. Naming the specific product (e.g.
                  &ldquo;Exchange Server&rdquo; or &ldquo;Webex&rdquo;) narrows
                  vulnerability alerts to vulnerabilities affecting that exact
                  product instead of every CVE under the vendor.
                </p>
                <input
                  id="primary_product"
                  type="text"
                  value={form.primary_product}
                  onChange={(e) => updateField("primary_product", e.target.value)}
                  placeholder="Exchange Server, IOS XE, Confluence…"
                  maxLength={255}
                  autoComplete="off"
                  disabled={!form.primary_vendor.trim()}
                />
              </div>
            </FormSection>
          </div>
        );

      case 2:
        return (
          <div className="intake-step-content">
            <FormSection
              title="Financial & Compliance Information"
              description="Optional: Helps improve economic impact analysis"
              required={false}
            >
              <div className="intake-form-group">
                <label htmlFor="revenue">
                  Annual Revenue
                  <RequiredBadge optional />
                </label>
                <select
                  id="revenue"
                  value={form.revenue_range}
                  onChange={(e) => updateField("revenue_range", e.target.value)}
                >
                  <option value="">Prefer not to say</option>
                  {REVENUE_RANGES.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>

              <div className="intake-form-group">
                <label>
                  Compliance Frameworks
                  <RequiredBadge optional />
                </label>
                <p className="intake-field-hint">
                  Select all that apply to your organization
                </p>
                <div className="intake-checkbox-group">
                  {COMPLIANCE_FRAMEWORKS.map((fw) => (
                    <label key={fw} className="intake-checkbox-label">
                      <input
                        type="checkbox"
                        checked={form.compliance_frameworks.includes(fw)}
                        onChange={() =>
                          toggleListItem("compliance_frameworks", fw)
                        }
                      />
                      {fw}
                    </label>
                  ))}
                </div>
              </div>
            </FormSection>
          </div>
        );

      case 3: {
        const categories = [...new Set(SECURITY_CONTROLS.map((c) => c.category))];
        return (
          <div className="intake-step-content">
            <FormSection
              title="Security Controls"
              description="Tell us which controls are in place. Answer as accurately as possible."
              required
            >
              {categories.map((cat) => (
                <div key={cat} className="intake-control-category">
                  <h4 className="intake-control-category-title">{cat}</h4>
                  {SECURITY_CONTROLS.filter((c) => c.category === cat).map(
                    (control) => {
                      const val = form.security_controls[control.key] ?? "unsure";
                      return (
                        <div key={control.key} className="intake-control-row">
                          <div className="intake-control-label-group">
                            <label className="intake-control-label">
                              {control.label}
                            </label>
                            <p className="intake-control-hint">{control.hint}</p>
                          </div>
                          <div className="intake-control-options">
                            {(["yes", "no", "unsure"] as const).map((option) => (
                              <button
                                key={option}
                                type="button"
                                className={`intake-control-btn ${
                                  val === option ? "active" : ""
                                }`}
                                onClick={() => setControlValue(control.key, option)}
                              >
                                {option.charAt(0).toUpperCase() + option.slice(1)}
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    }
                  )}
                </div>
              ))}
            </FormSection>
          </div>
        );
      }

      case 4:
        return (
          <div className="intake-step-content">
            <FormSection
              title="Technology & Infrastructure"
              description="Optional: Adds vendor and data intelligence"
              required={false}
            >
              <div className="intake-form-group">
                <label>
                  Cloud Providers in Use
                  <RequiredBadge optional />
                </label>
                <p className="intake-field-hint">Select all that apply</p>
                <div className="intake-checkbox-group">
                  {CLOUD_PROVIDERS.map((provider) => (
                    <label key={provider} className="intake-checkbox-label">
                      <input
                        type="checkbox"
                        checked={form.cloud_providers.includes(provider)}
                        onChange={() =>
                          toggleListItem("cloud_providers", provider)
                        }
                      />
                      {provider}
                    </label>
                  ))}
                </div>
              </div>

              <div className="intake-form-group">
                <label>
                  Data Types Handled
                  <RequiredBadge optional />
                </label>
                <p className="intake-field-hint">
                  Select all data types your organization processes
                </p>
                <div className="intake-checkbox-group">
                  {DATA_TYPES.map((dt) => (
                    <label key={dt} className="intake-checkbox-label">
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
            </FormSection>
          </div>
        );

      case 5:
        return (
          <div className="intake-step-content">
            <div className="intake-review-container">
              <h3>Review Your Assessment Intake</h3>
              <p className="intake-review-subtitle">
                Verify your information is correct before submitting
              </p>

              {intakeData && (
                <ProgressSummary
                  currentTier={intakeData.current_tier}
                  nextTier={intakeData.next_tier}
                  nextTierProgress={intakeData.next_tier_progress}
                  fieldsToAdvance={intakeData.fields_to_advance}
                  tierDefinitions={intakeData.tiers}
                />
              )}

              <div className="intake-review-section">
                <h4>Company Information</h4>
                <div className="intake-review-grid">
                  <div className="intake-review-item">
                    <span className="intake-review-label">Company Name:</span>
                    <span className="intake-review-value">{form.name || "-"}</span>
                  </div>
                  <div className="intake-review-item">
                    <span className="intake-review-label">Industry:</span>
                    <span className="intake-review-value">
                      {form.industry_label || "-"}
                    </span>
                  </div>
                  <div className="intake-review-item">
                    <span className="intake-review-label">State:</span>
                    <span className="intake-review-value">
                      {form.primary_state || "-"}
                    </span>
                  </div>
                  <div className="intake-review-item">
                    <span className="intake-review-label">Employee Count:</span>
                    <span className="intake-review-value">
                      {form.employee_range || "-"}
                    </span>
                  </div>
                  <div className="intake-review-item">
                    <span className="intake-review-label">Primary Domain:</span>
                    <span className="intake-review-value">
                      {form.primary_domain.trim() || "-"}
                    </span>
                  </div>
                  <div className="intake-review-item">
                    <span className="intake-review-label">Primary Vendor:</span>
                    <span className="intake-review-value">
                      {form.primary_vendor.trim() || "-"}
                    </span>
                  </div>
                </div>
              </div>

              {(form.revenue_range ||
                form.compliance_frameworks.length > 0) && (
                <div className="intake-review-section">
                  <h4>Financial & Compliance</h4>
                  <div className="intake-review-grid">
                    {form.revenue_range && (
                      <div className="intake-review-item">
                        <span className="intake-review-label">Revenue:</span>
                        <span className="intake-review-value">
                          {form.revenue_range}
                        </span>
                      </div>
                    )}
                    {form.compliance_frameworks.length > 0 && (
                      <div className="intake-review-item">
                        <span className="intake-review-label">
                          Compliance Frameworks:
                        </span>
                        <span className="intake-review-value">
                          {form.compliance_frameworks.join(", ")}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {Object.keys(form.security_controls).length > 0 && (
                <div className="intake-review-section">
                  <h4>Security Controls</h4>
                  <p className="intake-review-controls-summary">
                    {Object.values(form.security_controls).filter(
                      (v) => v === "yes"
                    ).length}{" "}
                    Yes, {Object.values(form.security_controls).filter(
                      (v) => v === "no"
                    ).length}{" "}
                    No,{" "}
                    {Object.values(form.security_controls).filter(
                      (v) => v === "unsure"
                    ).length}{" "}
                    Unsure
                  </p>
                </div>
              )}

              {(form.cloud_providers.length > 0 || form.data_types.length > 0) && (
                <div className="intake-review-section">
                  <h4>Technology & Infrastructure</h4>
                  <div className="intake-review-grid">
                    {form.cloud_providers.length > 0 && (
                      <div className="intake-review-item">
                        <span className="intake-review-label">
                          Cloud Providers:
                        </span>
                        <span className="intake-review-value">
                          {form.cloud_providers.join(", ")}
                        </span>
                      </div>
                    )}
                    {form.data_types.length > 0 && (
                      <div className="intake-review-item">
                        <span className="intake-review-label">Data Types:</span>
                        <span className="intake-review-value">
                          {form.data_types.join(", ")}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  if (!user) return null;

  return (
    <div className="intake-page">
      <div className="intake-container">
        <header className="intake-header">
          <h1>Assessment Intake Wizard</h1>
          <p className="intake-header-subtitle">
            Tell us about your organization to unlock actionable threat intelligence
          </p>
        </header>

        {step < 5 && (
          <IntakeProgressIndicator preview={preview} loading={previewLoading} />
        )}

        <StepIndicator currentStep={step} totalSteps={TOTAL_STEPS} steps={STEPS} />

        {error && <div className="intake-error">{error}</div>}

        {intakeLoading && step === 5 ? (
          <div className="intake-loading">Loading tier information...</div>
        ) : (
          renderStep()
        )}

        <div className="intake-actions">
          <button
            type="button"
            className="intake-btn intake-btn-secondary"
            onClick={handleBack}
            disabled={step === 1}
          >
            ← Previous
          </button>
          <button
            type="button"
            className="intake-btn intake-btn-primary"
            onClick={handleNext}
            disabled={submitting || advancing || !canAdvanceFromStep()}
          >
            {submitting || advancing
              ? (step === TOTAL_STEPS ? "Saving..." : "Saving…")
              : (step === TOTAL_STEPS ? "Complete" : "Next →")}
          </button>
        </div>
      </div>
    </div>
  );
}
