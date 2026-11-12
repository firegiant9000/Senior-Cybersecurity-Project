import { useState, useEffect, useRef } from "react";
import { useUserContext } from "../../context/UserContext";
import { updateOrganization } from "../../api/organizations";
import { createVendor } from "../../api/vendors";
import type { SectionProps } from "./types";

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
  { key: "mfa_enabled", label: "MFA enabled for all users", category: "Identity & Access" },
  { key: "password_policy", label: "Password policy enforced", category: "Identity & Access" },
  { key: "sso_in_use", label: "SSO in use", category: "Identity & Access" },
  { key: "edr_deployed", label: "EDR/antivirus deployed", category: "Endpoint Protection" },
  { key: "devices_encrypted", label: "Devices encrypted", category: "Endpoint Protection" },
  { key: "auto_patching", label: "Auto-patching enabled", category: "Endpoint Protection" },
  { key: "email_filtering", label: "Email filtering / gateway", category: "Email Security" },
  { key: "phishing_training", label: "Phishing training conducted", category: "Email Security" },
  { key: "firewall_in_place", label: "Firewall in place", category: "Network" },
  { key: "vpn_remote_access", label: "VPN for remote access", category: "Network" },
  { key: "network_segmentation", label: "Network segmentation", category: "Network" },
  { key: "regular_backups", label: "Regular data backups", category: "Data Protection" },
  { key: "backup_testing", label: "Backup restoration tested", category: "Data Protection" },
  { key: "data_classification", label: "Data classification policy", category: "Data Protection" },
  { key: "ir_plan_documented", label: "IR plan documented", category: "Incident Response" },
  { key: "ir_plan_tested", label: "IR plan tested within 12 months", category: "Incident Response" },
] as const;

const DEVICE_COUNT_RANGES = [
  "1-10", "11-50", "51-200", "201-500", "501-1000", "1001+",
] as const;

const INCIDENT_HISTORY_OPTIONS = [
  { value: "none", label: "No incidents" },
  { value: "ransomware", label: "Ransomware" },
  { value: "phishing", label: "Phishing / BEC" },
  { value: "data_breach", label: "Data breach" },
  { value: "malware", label: "Malware" },
  { value: "insider_threat", label: "Insider threat" },
  { value: "other", label: "Other" },
] as const;

export default function SecurityProfileSection({
  orgId,
  canEdit,
  onChanged,
  onVendorsSynced,
}: SectionProps & { onVendorsSynced: () => void }) {
  const { organization, refreshOrganization } = useUserContext();

  // Fields start from the organization already loaded, so the first render is
  // correct and the sync effect below does not overwrite an early edit.
  const [securityControls, setSecurityControls] = useState<Record<string, "yes" | "no" | "unsure">>(
    () => (organization?.security_controls ?? {}) as Record<string, "yes" | "no" | "unsure">,
  );
  const [cloudProviders, setCloudProviders] = useState<string[]>(() => organization?.cloud_providers ?? []);
  const [complianceFrameworks, setComplianceFrameworks] = useState<string[]>(
    () => organization?.compliance_frameworks ?? [],
  );
  const [dataTypes, setDataTypes] = useState<string[]>(() => organization?.data_types ?? []);
  const [deviceCountRange, setDeviceCountRange] = useState(() => organization?.device_count_range ?? "");
  const [incidentHistory, setIncidentHistory] = useState(() => organization?.incident_history ?? "");
  const [secProfileSaveMsg, setSecProfileSaveMsg] = useState("");
  const [secProfileSaveErr, setSecProfileSaveErr] = useState("");
  const [secProfileSaving, setSecProfileSaving] = useState(false);
  const syncedOrganization = useRef(organization);

  // Re-sync security profile fields when a different organization object arrives
  useEffect(() => {
    if (!organization || organization === syncedOrganization.current) return;
    syncedOrganization.current = organization;
    setSecurityControls((organization.security_controls ?? {}) as Record<string, "yes" | "no" | "unsure">);
    setCloudProviders(organization.cloud_providers ?? []);
    setComplianceFrameworks(organization.compliance_frameworks ?? []);
    setDataTypes(organization.data_types ?? []);
    setDeviceCountRange(organization.device_count_range ?? "");
    setIncidentHistory(organization.incident_history ?? "");
  }, [organization]);

  const toggleSecProfileItem = (
    field: "cloudProviders" | "complianceFrameworks" | "dataTypes",
    value: string,
  ) => {
    const setters = {
      cloudProviders: setCloudProviders,
      complianceFrameworks: setComplianceFrameworks,
      dataTypes: setDataTypes,
    };
    setters[field]((prev) => {
      return prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value];
    });
  };

  const handleSaveSecurityProfile = async () => {
    if (!canEdit) return;
    setSecProfileSaveMsg("");
    setSecProfileSaveErr("");
    setSecProfileSaving(true);
    try {
      await updateOrganization(orgId, {
        security_controls: Object.keys(securityControls).length > 0 ? securityControls : null,
        cloud_providers: cloudProviders.length > 0 ? cloudProviders : null,
        compliance_frameworks: complianceFrameworks.length > 0 ? complianceFrameworks : null,
        data_types: dataTypes.length > 0 ? dataTypes : null,
        device_count_range: deviceCountRange || null,
        incident_history: incidentHistory || null,
      });
      setSecProfileSaveMsg("Security profile saved.");
      await refreshOrganization();
      // Sync checked cloud providers into the vendor tech stack. Backend
      // dedupes via the (org, vendor, product) unique constraint when
      // ?idempotent=true, so existing rows are returned unchanged instead
      // of duplicated. We can't dedupe on the client because the vendor list
      // only holds the current paginated page.
      if (cloudProviders.length > 0) {
        await Promise.allSettled(
          cloudProviders.map((p) => createVendor(orgId, p, "", { idempotent: true })),
        );
        onVendorsSynced();
      }
      onChanged();
    } catch (err) {
      setSecProfileSaveErr(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSecProfileSaving(false);
    }
  };

  return (
    <div className="section-accordion-body">
      {secProfileSaveMsg && (
        <div className="settings-action-msg">{secProfileSaveMsg}</div>
      )}
      {secProfileSaveErr && (
        <div className="settings-error" style={{ marginBottom: "0.75rem" }}>
          {secProfileSaveErr}
        </div>
      )}

      <div className="sec-profile-subsection">
        <h3 className="sec-profile-subtitle">Security Controls</h3>
        {[...new Set(SECURITY_CONTROLS.map((c) => c.category))].map((cat) => (
          <div key={cat} className="sec-control-group">
            <h4 className="sec-control-category">{cat}</h4>
            {SECURITY_CONTROLS.filter((c) => c.category === cat).map((control) => {
              const val = securityControls[control.key] ?? "unsure";
              return (
                <div key={control.key} className="sec-control-row">
                  <span className="sec-control-label">{control.label}</span>
                  <div className="sec-control-toggle">
                    {(["yes", "no", "unsure"] as const).map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        className={`sec-control-option${val === opt ? " selected" : ""}`}
                        onClick={() =>
                          setSecurityControls((prev) => ({ ...prev, [control.key]: opt }))
                        }
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

      <div className="sec-profile-subsection">
        <h3 className="sec-profile-subtitle">Cloud & SaaS Providers</h3>
        <div className="sec-checklist">
          {CLOUD_PROVIDERS.map((provider) => (
            <label key={provider} className="sec-check-item">
              <input
                type="checkbox"
                checked={cloudProviders.includes(provider)}
                onChange={() => toggleSecProfileItem("cloudProviders", provider)}
              />
              {provider}
            </label>
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
          Checked providers are automatically added to Your Technology Stack for vulnerability monitoring.
        </p>
      </div>

      <div className="sec-profile-subsection">
        <h3 className="sec-profile-subtitle">Compliance Frameworks</h3>
        <div className="sec-checklist">
          {COMPLIANCE_FRAMEWORKS.map((fw) => (
            <label key={fw} className="sec-check-item">
              <input
                type="checkbox"
                checked={complianceFrameworks.includes(fw)}
                onChange={() => toggleSecProfileItem("complianceFrameworks", fw)}
              />
              {fw}
            </label>
          ))}
        </div>
      </div>

      <div className="sec-profile-subsection">
        <h3 className="sec-profile-subtitle">Data Types Handled</h3>
        <div className="sec-checklist">
          {DATA_TYPES.map((dt) => (
            <label key={dt} className="sec-check-item">
              <input
                type="checkbox"
                checked={dataTypes.includes(dt)}
                onChange={() => toggleSecProfileItem("dataTypes", dt)}
              />
              {dt}
            </label>
          ))}
        </div>
      </div>

      <div className="sec-profile-subsection">
        <h3 className="sec-profile-subtitle">Additional Context</h3>
        <div className="sec-profile-field-row">
          <label htmlFor="device-count">Approximate device count</label>
          <select
            id="device-count"
            className="member-role-select"
            value={deviceCountRange}
            onChange={(e) => setDeviceCountRange(e.target.value)}
          >
            <option value="">Not set</option>
            {DEVICE_COUNT_RANGES.map((r) => (
              <option key={r} value={r}>{r} devices</option>
            ))}
          </select>
        </div>
        <div className="sec-profile-field-row">
          <label htmlFor="incident-history">Prior cyber incidents (past 24 months)</label>
          <select
            id="incident-history"
            className="member-role-select"
            value={incidentHistory}
            onChange={(e) => setIncidentHistory(e.target.value)}
          >
            <option value="">Not set</option>
            {INCIDENT_HISTORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="settings-actions" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className="action-btn"
          disabled={secProfileSaving}
          onClick={() => void handleSaveSecurityProfile()}
        >
          {secProfileSaving ? "Saving..." : "Save security profile"}
        </button>
      </div>
    </div>
  );
}
