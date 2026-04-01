import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
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

interface FormData {
  name: string;
  industry_label: string;
  primary_state: string;
  employee_range: string;
  revenue_range: string;
}

const TOTAL_STEPS = 5;

export default function OnboardingPage({ onComplete }: { onComplete: () => void }) {
  const navigate = useNavigate();
  const { orgId } = useAuth();

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
  });

  const update = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setError("");
  };

  const canAdvance = (): boolean => {
    switch (step) {
      case 1: return form.name.trim().length >= 1;
      case 2: return form.industry_label !== "";
      case 3: return form.primary_state !== "";
      case 4: return form.employee_range !== "";
      case 5: return true; // revenue is optional
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

    const payload: Record<string, string | null> = {
      name: form.name.trim(),
      industry_label: form.industry_label,
      primary_state: form.primary_state,
      employee_range: form.employee_range,
      revenue_range: form.revenue_range || null,
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

      onComplete();
      navigate("/");
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
      default:
        return null;
    }
  };

  return (
    <div className="onboarding-page">
      <div className="onboarding-card">
        <div className="onboarding-header">
          <h1>Set Up Your Organization</h1>
          <p>Step {step} of {TOTAL_STEPS}</p>
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

        {step === 5 && !form.revenue_range && (
          <button
            type="button"
            className="onboarding-skip-btn"
            onClick={handleSubmit}
            disabled={submitting}
          >
            Skip and finish
          </button>
        )}
      </div>
    </div>
  );
}
