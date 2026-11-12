import { useState } from "react";
import { useUserContext } from "../../context/UserContext";
import { updateOrganization } from "../../api/organizations";
import { httpUrlOrNull } from "../../utils/safeUrl";
import type { SectionProps } from "./types";

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

export default function CompanySection({ orgId, canEdit, onChanged }: SectionProps) {
  const {
    organization,
    refreshOrganization,
    loading: orgLoading,
    error: orgError,
  } = useUserContext();

  const [companyNameField, setCompanyNameField] = useState(() => organization?.name ?? "");
  const [logoUrlField, setLogoUrlField] = useState(() => organization?.logo_url ?? "");
  const [primaryDomainField, setPrimaryDomainField] = useState(() => organization?.primary_domain ?? "");
  const [industryLabelField, setIndustryLabelField] = useState(() => organization?.industry_label ?? "");
  const [companySaveMsg, setCompanySaveMsg] = useState("");
  const [companySaveErr, setCompanySaveErr] = useState("");
  const [companySaving, setCompanySaving] = useState(false);

  // Re-sync the fields when a different organization object arrives. This is
  // done during render, not in an effect, so the fields never commit with stale
  // values and an edit made right after they appear is not overwritten.
  const [syncedOrganization, setSyncedOrganization] = useState(organization);
  if (organization && organization !== syncedOrganization) {
    setSyncedOrganization(organization);
    setCompanyNameField(organization.name);
    setLogoUrlField(organization.logo_url ?? "");
    setPrimaryDomainField(organization.primary_domain ?? "");
    setIndustryLabelField(organization.industry_label ?? "");
  }

  const companyFieldsDisabled = orgLoading || !organization || !canEdit;
  const logoPreviewUrl = httpUrlOrNull(logoUrlField);

  const handleSaveCompanyProfile = async () => {
    if (!canEdit) return;
    setCompanySaveMsg("");
    setCompanySaveErr("");
    setCompanySaving(true);
    try {
      await updateOrganization(orgId, {
        name: companyNameField.trim(),
        logo_url: logoUrlField.trim() || null,
        primary_domain: primaryDomainField.trim() || null,
        industry_label: industryLabelField || null,
      });
      setCompanySaveMsg("Company profile saved.");
      await refreshOrganization();
      onChanged();
    } catch (err) {
      setCompanySaveErr(err instanceof Error ? err.message : "Save failed");
    } finally {
      setCompanySaving(false);
    }
  };

  return (
    <div className="section-accordion-body">
      {!canEdit && (
        <p className="settings-readonly-hint">
          Only organization owners, organization admins, or platform
          admins can edit these fields.
        </p>
      )}
      {orgLoading && !organization && (
        <p className="settings-loading">Loading organization...</p>
      )}
      {orgError && (
        <div className="settings-error">
          Could not load organization profile.
        </div>
      )}
      {organization && (
        <>
          {companySaveMsg && (
            <div className="settings-action-msg">
              {companySaveMsg}
            </div>
          )}
          {companySaveErr && (
            <div
              className="settings-error"
              style={{ marginBottom: "0.75rem" }}
            >
              {companySaveErr}
            </div>
          )}
          <div className="settings-field company-profile-field">
            <label htmlFor="company-name">Name</label>
            <input
              id="company-name"
              className="company-profile-input"
              type="text"
              value={companyNameField}
              onChange={(e) => setCompanyNameField(e.target.value)}
              disabled={companyFieldsDisabled}
              autoComplete="organization"
            />
          </div>
          <div className="settings-field company-profile-field">
            <label htmlFor="company-logo">Logo</label>
            <div className="company-logo-input-col">
              <input
                id="company-logo"
                className="company-profile-input"
                type="url"
                placeholder="https://..."
                value={logoUrlField}
                onChange={(e) => setLogoUrlField(e.target.value)}
                disabled={companyFieldsDisabled}
              />
              {logoPreviewUrl !== null && (
                <img
                  className="company-logo-preview"
                  src={logoPreviewUrl}
                  alt=""
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
              )}
            </div>
          </div>
          <div className="settings-field company-profile-field">
            <label htmlFor="company-domain">Domain</label>
            <input
              id="company-domain"
              className="company-profile-input"
              type="text"
              placeholder="example.com"
              value={primaryDomainField}
              onChange={(e) =>
                setPrimaryDomainField(e.target.value)
              }
              disabled={companyFieldsDisabled}
              autoCapitalize="none"
            />
          </div>
          <div className="settings-field company-profile-field">
            <label htmlFor="company-industry">Industry</label>
            <select
              id="company-industry"
              className="company-profile-input"
              value={industryLabelField}
              onChange={(e) => setIndustryLabelField(e.target.value)}
              disabled={companyFieldsDisabled}
            >
              <option value="">Select industry…</option>
              {INDUSTRY_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
          {canEdit && (
            <div
              className="settings-actions"
              style={{ marginTop: "1rem" }}
            >
              <button
                type="button"
                className="action-btn"
                disabled={companySaving || !companyNameField.trim()}
                onClick={() => void handleSaveCompanyProfile()}
              >
                {companySaving ? "Saving..." : "Save company profile"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
