import { useState } from "react";
import { useUserContext } from "../../context/UserContext";
import { updateOrganization } from "../../api/organizations";
import { httpUrlOrNull } from "../../utils/safeUrl";
import { OrgBasicsFields } from "../../components/org/OrgBasicsFields";
import { RevenueField, toNullable } from "../../components/org/RevenueField";
import type { SectionProps } from "./types";

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
  const [primaryStateField, setPrimaryStateField] = useState(() => organization?.primary_state ?? "");
  const [employeeRangeField, setEmployeeRangeField] = useState(() => organization?.employee_range ?? "");
  const [revenueRangeField, setRevenueRangeField] = useState(() => organization?.revenue_range ?? "");
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
    setPrimaryStateField(organization.primary_state ?? "");
    setEmployeeRangeField(organization.employee_range ?? "");
    setRevenueRangeField(organization.revenue_range ?? "");
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
        logo_url: toNullable(logoUrlField),
        primary_domain: toNullable(primaryDomainField),
        industry_label: toNullable(industryLabelField),
        primary_state: toNullable(primaryStateField),
        employee_range: toNullable(employeeRangeField),
        revenue_range: toNullable(revenueRangeField),
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
          <OrgBasicsFields
            value={{
              name: companyNameField,
              industry_label: industryLabelField,
              primary_state: primaryStateField,
              employee_range: employeeRangeField,
              primary_domain: primaryDomainField,
            }}
            onChange={(patch) => {
              if (patch.name !== undefined) setCompanyNameField(patch.name);
              if (patch.industry_label !== undefined) setIndustryLabelField(patch.industry_label);
              if (patch.primary_state !== undefined) setPrimaryStateField(patch.primary_state);
              if (patch.employee_range !== undefined) setEmployeeRangeField(patch.employee_range);
              if (patch.primary_domain !== undefined) setPrimaryDomainField(patch.primary_domain);
            }}
            disabled={companyFieldsDisabled}
          />
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
          <RevenueField
            value={revenueRangeField}
            onChange={setRevenueRangeField}
            disabled={companyFieldsDisabled}
          />
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
