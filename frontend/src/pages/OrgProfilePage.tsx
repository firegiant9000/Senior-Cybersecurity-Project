import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useUserContext } from "../context/UserContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import { canEditOrganizationProfile } from "../components/ProtectedRoute";
import {
  OrgVendor,
  OrgVendorImportPreviewResponse,
  VendorSuggestion,
  listVendors,
  createVendor,
  deleteVendor,
  importVendorsCsv,
  previewVendorsCsv,
  suggestVendors,
  autocompleteVendors,
} from "../api/vendors";
import {
  OrgDomain,
  listDomains,
  addDomain,
  deleteDomain,
} from "../api/domains";
import {
  OrgUpload,
  listUploads,
  uploadFile,
  deleteUpload,
  downloadUpload,
} from "../api/uploads";
import AssessmentReadinessWidget from "../components/AssessmentReadiness";
import ValidationPanel from "../components/ValidationPanel";
import "../Dashboard.css";
import "./SettingsPage.css";

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

interface UserProfile {
  id: number;
  email: string;
  is_active: boolean;
  role: string;
  auth_provider: string;
  created_at: string;
  org_id: number | null;
  org_role: string | null;
}

export default function OrgProfilePage() {
  const {
    organization,
    refreshOrganization,
    loading: orgLoading,
    error: orgError,
  } = useUserContext();
  const navigate = useNavigate();
  const location = useLocation();

  // Scroll to a specific section when navigated here from AssessmentReadiness Fix button
  useEffect(() => {
    const state = location.state as { scrollTo?: string } | null;
    if (state?.scrollTo) {
      const el = document.getElementById(state.scrollTo);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [location.state]);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    company: true,
    security: false,
    vendors: false,
    domains: false,
    uploads: false,
  });
  const toggleSection = (key: string) =>
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));

  const [companyNameField, setCompanyNameField] = useState("");
  const [logoUrlField, setLogoUrlField] = useState("");
  const [primaryDomainField, setPrimaryDomainField] = useState("");
  const [industryLabelField, setIndustryLabelField] = useState("");
  const [companySaveMsg, setCompanySaveMsg] = useState("");
  const [companySaveErr, setCompanySaveErr] = useState("");
  const [companySaving, setCompanySaving] = useState(false);

  // Security profile state
  const [securityControls, setSecurityControls] = useState<Record<string, "yes" | "no" | "unsure">>({});
  const [cloudProviders, setCloudProviders] = useState<string[]>([]);
  const [complianceFrameworks, setComplianceFrameworks] = useState<string[]>([]);
  const [dataTypes, setDataTypes] = useState<string[]>([]);
  const [deviceCountRange, setDeviceCountRange] = useState("");
  const [incidentHistory, setIncidentHistory] = useState("");
  const [secProfileSaveMsg, setSecProfileSaveMsg] = useState("");
  const [secProfileSaveErr, setSecProfileSaveErr] = useState("");
  const [secProfileSaving, setSecProfileSaving] = useState(false);

  // Vendor / Tech Stack state
  const [vendors, setVendors] = useState<OrgVendor[]>([]);
  const [vendorTotal, setVendorTotal] = useState(0);
  const [vendorPage, setVendorPage] = useState(1);
  const [vendorLoading, setVendorLoading] = useState(false);
  const [vendorError, setVendorError] = useState("");
  const [vendorMsg, setVendorMsg] = useState("");
  const [newVendor, setNewVendor] = useState("");
  const [newProduct, setNewProduct] = useState("");
  const [vendorSuggestions, setVendorSuggestions] = useState<VendorSuggestion[]>([]);
  const [productSuggestions, setProductSuggestions] = useState<string[]>([]);
  const [showVendorSuggestions, setShowVendorSuggestions] = useState(false);
  const [showProductSuggestions, setShowProductSuggestions] = useState(false);
  const vendorInputRef = useRef<HTMLInputElement>(null);
  const productInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadFileInputRef = useRef<HTMLInputElement>(null);
  const vendorPageSize = 20;

  // CSV preview state
  const [csvPreview, setCsvPreview] = useState<OrgVendorImportPreviewResponse | null>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvPreviewing, setCsvPreviewing] = useState(false);

  // Domain state
  const [domains, setDomains] = useState<OrgDomain[]>([]);
  const [domainTotal, setDomainTotal] = useState(0);
  const [domainPage, setDomainPage] = useState(1);
  const [domainLoading, setDomainLoading] = useState(false);
  const [domainError, setDomainError] = useState("");
  const [domainMsg, setDomainMsg] = useState("");
  const [newDomain, setNewDomain] = useState("");
  const domainPageSize = 20;

  // Upload state
  const [uploads, setUploads] = useState<OrgUpload[]>([]);
  const [uploadTotal, setUploadTotal] = useState(0);
  const [uploadPage, setUploadPage] = useState(1);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");

  const loadVendors = useCallback(async (orgId: number, page: number) => {
    setVendorLoading(true);
    setVendorError("");
    try {
      const data = await listVendors(orgId, page, vendorPageSize);
      setVendors(data.items);
      setVendorTotal(data.total);
    } catch {
      setVendorError("Failed to load technology stack");
    } finally {
      setVendorLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile?.org_id) {
      loadVendors(profile.org_id, vendorPage);
    }
  }, [profile?.org_id, vendorPage, loadVendors]);

  useEffect(() => {
    if (loading || !location.hash) return;
    const hashToSection: Record<string, string> = {
      '#section-security-profile': 'security',
      '#section-vendors': 'vendors',
      '#section-domains': 'domains',
      '#section-uploads': 'uploads',
    };
    const sectionKey = hashToSection[location.hash];
    if (sectionKey) setOpenSections(prev => ({ ...prev, [sectionKey]: true }));
    const el = document.getElementById(location.hash.slice(1));
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [location.hash, loading]);

  const handleAddVendor = async () => {
    if (!profile?.org_id || !newVendor.trim()) return;
    setVendorError("");
    const normalizedNew = newVendor.trim().replace(/\s+/g, " ").toLowerCase();
    const normalizedProd = newProduct.trim().replace(/\s+/g, " ").toLowerCase();
    const isDupe = vendors.some(
      (v) =>
        v.vendor_name.toLowerCase() === normalizedNew &&
        v.product_name.toLowerCase() === normalizedProd,
    );
    if (isDupe) {
      setVendorError("A vendor with this name already exists in your stack.");
      return;
    }
    try {
      await createVendor(profile.org_id, newVendor.trim(), newProduct.trim());
      setNewVendor("");
      setNewProduct("");
      setVendorMsg("Vendor added");
      setVendorPage(1);
      loadVendors(profile.org_id, 1);
    } catch (err) {
      setVendorError(
        err instanceof Error ? err.message : "Failed to add vendor",
      );
    }
  };

  const handleDeleteVendor = async (vendorId: number) => {
    if (!profile?.org_id) return;
    setVendorError("");
    try {
      await deleteVendor(profile.org_id, vendorId);
      setVendorPage(1);
      loadVendors(profile.org_id, 1);
    } catch {
      setVendorError("Failed to remove vendor");
    }
  };

  const handleCsvImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !profile?.org_id) return;
    setVendorError("");
    setVendorMsg("");
    setCsvPreviewing(true);
    try {
      const preview = await previewVendorsCsv(profile.org_id, file);
      setCsvPreview(preview);
      setCsvFile(file);
    } catch (err) {
      setVendorError(err instanceof Error ? err.message : "CSV preview failed");
    } finally {
      setCsvPreviewing(false);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleCsvConfirm = async () => {
    if (!csvFile || !profile?.org_id) return;
    setVendorError("");
    setVendorMsg("");
    try {
      const result = await importVendorsCsv(profile.org_id, csvFile);
      const parts: string[] = [];
      if (result.imported) parts.push(`${result.imported} imported`);
      if (result.skipped) parts.push(`${result.skipped} duplicates skipped`);
      if (result.errors.length) parts.push(`${result.errors.length} errors`);
      if (!result.imported && !result.skipped && !result.errors.length) {
        setVendorError("CSV contained no valid vendor rows");
      } else {
        setVendorMsg(parts.join(", "));
      }
      if (result.errors.length) {
        setVendorError(result.errors.slice(0, 5).join("\n"));
      }
      loadVendors(profile.org_id, 1);
      setVendorPage(1);
    } catch (err) {
      setVendorError(err instanceof Error ? err.message : "CSV import failed");
    } finally {
      setCsvPreview(null);
      setCsvFile(null);
    }
  };

  const handleCsvCancel = () => {
    setCsvPreview(null);
    setCsvFile(null);
  };

  // ── Domain handlers ──────────────────────────────────────────────────
  const loadDomains = useCallback(async (orgId: number, page: number) => {
    setDomainLoading(true);
    setDomainError("");
    try {
      const data = await listDomains(orgId, page, domainPageSize);
      setDomains(data.items);
      setDomainTotal(data.total);
    } catch {
      setDomainError("Failed to load domains");
    } finally {
      setDomainLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile?.org_id) loadDomains(profile.org_id, domainPage);
  }, [profile?.org_id, domainPage, loadDomains]);

  const handleAddDomain = async () => {
    if (!profile?.org_id || !newDomain.trim()) return;
    setDomainError("");
    const cleaned = newDomain
      .trim()
      .replace(/^https?:\/\//i, "")
      .replace(/\/.*$/, "")
      .toLowerCase()
      .replace(/\.$/, "");
    const isDupe = domains.some((d) => d.domain_name.toLowerCase() === cleaned);
    if (isDupe) {
      setDomainError("This domain is already registered.");
      return;
    }
    try {
      await addDomain(profile.org_id, cleaned);
      setNewDomain("");
      setDomainMsg("Domain added");
      setDomainPage(1);
      loadDomains(profile.org_id, 1);
    } catch (err) {
      setDomainError(
        err instanceof Error ? err.message : "Failed to add domain",
      );
    }
  };

  const handleDeleteDomain = async (domainId: number) => {
    if (!profile?.org_id) return;
    setDomainError("");
    try {
      await deleteDomain(profile.org_id, domainId);
      setDomainPage(1);
      loadDomains(profile.org_id, 1);
    } catch {
      setDomainError("Failed to remove domain");
    }
  };

  // ── Upload handlers ─────────────────────────────────────────────────
  const loadUploads = useCallback(async (orgId: number, page: number) => {
    setUploadLoading(true);
    setUploadError("");
    try {
      const data = await listUploads(orgId, page);
      setUploads(data.items);
      setUploadTotal(data.total);
    } catch {
      setUploadError("Failed to load uploads");
    } finally {
      setUploadLoading(false);
    }
  }, []);

  useEffect(() => {
    if (profile?.org_id) loadUploads(profile.org_id, uploadPage);
  }, [profile?.org_id, uploadPage, loadUploads]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !profile?.org_id) return;
    setUploadError("");
    setUploadMsg("");
    try {
      await uploadFile(profile.org_id, file);
      setUploadMsg(`"${file.name}" uploaded successfully`);
      loadUploads(profile.org_id, 1);
      setUploadPage(1);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    }
    if (uploadFileInputRef.current) uploadFileInputRef.current.value = "";
  };

  const handleDeleteUpload = async (uploadId: number) => {
    if (!profile?.org_id) return;
    setUploadError("");
    try {
      await deleteUpload(profile.org_id, uploadId);
      setUploadPage(1);
      loadUploads(profile.org_id, 1);
    } catch {
      setUploadError("Failed to delete upload");
    }
  };

  const handleDownloadUpload = async (uploadId: number, filename: string) => {
    if (!profile?.org_id) return;
    try {
      await downloadUpload(profile.org_id, uploadId, filename);
    } catch {
      setUploadError("Failed to download file");
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Debounced typeahead for vendor name — uses fuzzy suggest endpoint with confidence scores
  useEffect(() => {
    if (newVendor.length < 2) {
      setVendorSuggestions([]);
      setShowVendorSuggestions(false);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await suggestVendors(newVendor);
        if (!cancelled) {
          setVendorSuggestions(results);
          setShowVendorSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) {
          setVendorSuggestions([]);
          setShowVendorSuggestions(false);
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [newVendor]);

  // Debounced autocomplete for product name
  useEffect(() => {
    if (newProduct.length < 2) {
      setProductSuggestions([]);
      setShowProductSuggestions(false);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await autocompleteVendors(
          newProduct,
          "product",
          newVendor || undefined,
        );
        if (!cancelled) {
          setProductSuggestions(results);
          setShowProductSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) {
          setProductSuggestions([]);
          setShowProductSuggestions(false);
        }
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [newProduct, newVendor]);

  // Sync company profile fields when organization data loads
  useEffect(() => {
    if (!organization) return;
    setCompanyNameField(organization.name);
    setLogoUrlField(organization.logo_url ?? "");
    setPrimaryDomainField(organization.primary_domain ?? "");
    setIndustryLabelField(organization.industry_label ?? "");
    setSecurityControls((organization.security_controls ?? {}) as Record<string, "yes" | "no" | "unsure">);
    setCloudProviders(organization.cloud_providers ?? []);
    setComplianceFrameworks(organization.compliance_frameworks ?? []);
    setDataTypes(organization.data_types ?? []);
    setDeviceCountRange(organization.device_count_range ?? "");
    setIncidentHistory(organization.incident_history ?? "");
  }, [organization]);

  const canEditOrgProfile =
    profile != null &&
    canEditOrganizationProfile(profile.role, profile.org_role);
  const companyFieldsDisabled =
    orgLoading || !organization || !canEditOrgProfile;

  const handleSaveCompanyProfile = async () => {
    if (!profile?.org_id || !canEditOrgProfile) return;
    setCompanySaveMsg("");
    setCompanySaveErr("");
    setCompanySaving(true);
    try {
      const body = {
        name: companyNameField.trim(),
        logo_url: logoUrlField.trim() || null,
        primary_domain: primaryDomainField.trim() || null,
        industry_label: industryLabelField || null,
      };
      const resp = await fetchWithAuth(
        `${API_BASE_URL}/api/v1/organizations/${profile.org_id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(detail || "Failed to save company profile");
      }
      setCompanySaveMsg("Company profile saved.");
      await refreshOrganization();
    } catch (err) {
      setCompanySaveErr(err instanceof Error ? err.message : "Save failed");
    } finally {
      setCompanySaving(false);
    }
  };

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
    if (!profile?.org_id || !canEditOrgProfile) return;
    setSecProfileSaveMsg("");
    setSecProfileSaveErr("");
    setSecProfileSaving(true);
    try {
      const body = {
        security_controls: Object.keys(securityControls).length > 0 ? securityControls : null,
        cloud_providers: cloudProviders.length > 0 ? cloudProviders : null,
        compliance_frameworks: complianceFrameworks.length > 0 ? complianceFrameworks : null,
        data_types: dataTypes.length > 0 ? dataTypes : null,
        device_count_range: deviceCountRange || null,
        incident_history: incidentHistory || null,
      };
      const resp = await fetchWithAuth(
        `${API_BASE_URL}/api/v1/organizations/${profile.org_id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(detail || "Failed to save security profile");
      }
      setSecProfileSaveMsg("Security profile saved.");
      await refreshOrganization();
      // Sync checked cloud providers into the vendor tech stack. Backend
      // dedupes via the (org, vendor, product) unique constraint when
      // ?idempotent=true, so existing rows are returned unchanged instead
      // of duplicated. We can't dedupe on the client because `vendors`
      // only holds the current paginated page.
      const orgId = profile.org_id;
      if (orgId != null && cloudProviders.length > 0) {
        await Promise.allSettled(
          cloudProviders.map((p) => createVendor(orgId, p, "", { idempotent: true })),
        );
        loadVendors(orgId, 1);
      }
    } catch (err) {
      setSecProfileSaveErr(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSecProfileSaving(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
        if (!resp.ok) throw new Error("Failed to load profile");
        const data: UserProfile = await resp.json();
        if (!cancelled) setProfile(data);
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Failed to load profile",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadProfile();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Organization Profile</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
          <button type="button" onClick={() => navigate("/settings")}>
            Account Settings
          </button>
        </div>
      </header>

      <div className="settings-page settings-page--embedded">
        <div className="settings-card settings-card--wide">
          {loading && <p className="settings-loading">Loading profile...</p>}
          {error && <div className="settings-error">{error}</div>}

          {!loading && !error && profile && (
            <div className="settings-sections">
              {profile.org_id == null && (
                <div className="settings-section">
                  <p style={{ color: 'var(--text-secondary, #555)', fontSize: 14, lineHeight: 1.6 }}>
                    You are not part of an organization yet.{' '}
                    <a href="/settings" style={{ color: 'var(--accent, #0b1060)', fontWeight: 600 }}>
                      Create or join an organization
                    </a>{' '}
                    to manage your profile, vendors, and domains.
                  </p>
                </div>
              )}
              {profile.org_id != null && <AssessmentReadinessWidget />}
              {profile.org_id != null && <ValidationPanel />}

              {profile.org_id != null && (
                <section className="settings-section">
                  <button className="section-accordion-header" onClick={() => toggleSection('company')} aria-expanded={openSections.company}>
                    <div className="section-accordion-header-text">
                      <span className="section-accordion-title">Company profile</span>
                      <span className="section-accordion-desc">Name, logo URL, and primary domain for your organization.</span>
                    </div>
                    <span className={`section-accordion-chevron${openSections.company ? ' open' : ''}`}>›</span>
                  </button>
                  {openSections.company && (
                    <div className="section-accordion-body">
                      {!canEditOrgProfile && (
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
                          {logoUrlField.trim() !== "" && (
                            <img
                              className="company-logo-preview"
                              src={logoUrlField.trim()}
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
                      {canEditOrgProfile && (
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
                  )}
                </section>
              )}

              {profile.org_id != null && organization && canEditOrgProfile && (
                <section id="section-security-profile" className="settings-section">
                  <button className="section-accordion-header" onClick={() => toggleSection('security')} aria-expanded={openSections.security}>
                    <div className="section-accordion-header-text">
                      <span className="section-accordion-title">Security Profile</span>
                      <span className="section-accordion-desc">Security controls, compliance, data handling, and incident history.</span>
                    </div>
                    <span className={`section-accordion-chevron${openSections.security ? ' open' : ''}`}>›</span>
                  </button>
                  {openSections.security && (
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
                  )}
                </section>
              )}

              {profile.org_id && (
                <section id="section-vendors" className="settings-section">
                  <button className="section-accordion-header" onClick={() => toggleSection('vendors')} aria-expanded={openSections.vendors}>
                    <div className="section-accordion-header-text">
                      <span className="section-accordion-title">Your Technology Stack</span>
                      <span className="section-accordion-desc">Track vendors and products your organization uses.</span>
                    </div>
                    <span className={`section-accordion-chevron${openSections.vendors ? ' open' : ''}`}>›</span>
                  </button>
                  {openSections.vendors && (
                    <div className="section-accordion-body">
                      {vendorMsg && (
                    <div className="settings-action-msg">{vendorMsg}</div>
                  )}
                  {vendorError && (
                    <div
                      className="settings-error"
                      style={{
                        whiteSpace: "pre-line",
                        marginBottom: "0.75rem",
                      }}
                    >
                      {vendorError}
                    </div>
                  )}

                  <div className="vendor-add-form">
                    <div className="vendor-input-wrapper">
                      <input
                        ref={vendorInputRef}
                        type="text"
                        placeholder="Vendor name"
                        value={newVendor}
                        onChange={(e) => setNewVendor(e.target.value)}
                        onFocus={() =>
                          vendorSuggestions.length > 0 &&
                          setShowVendorSuggestions(true)
                        }
                        onBlur={() =>
                          setTimeout(() => setShowVendorSuggestions(false), 200)
                        }
                      />
                      {showVendorSuggestions && (
                        <ul className="autocomplete-dropdown">
                          {vendorSuggestions.map((s) => (
                            <li
                              key={s.vendor_name}
                              onMouseDown={() => {
                                setNewVendor(s.vendor_name);
                                setShowVendorSuggestions(false);
                              }}
                              title={`${Math.round(s.score * 100)}% match`}
                              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}
                            >
                              <span>{s.vendor_name}</span>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted)', flexShrink: 0 }}>
                                {Math.round(s.score * 100)}%
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div className="vendor-input-wrapper">
                      <input
                        ref={productInputRef}
                        type="text"
                        placeholder="Product name (optional)"
                        value={newProduct}
                        onChange={(e) => setNewProduct(e.target.value)}
                        onFocus={() =>
                          productSuggestions.length > 0 &&
                          setShowProductSuggestions(true)
                        }
                        onBlur={() =>
                          setTimeout(
                            () => setShowProductSuggestions(false),
                            200,
                          )
                        }
                      />
                      {showProductSuggestions && (
                        <ul className="autocomplete-dropdown">
                          {productSuggestions.map((s) => (
                            <li
                              key={s}
                              onMouseDown={() => {
                                setNewProduct(s);
                                setShowProductSuggestions(false);
                              }}
                            >
                              {s}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <button
                      className="action-btn"
                      onClick={handleAddVendor}
                      disabled={!newVendor.trim()}
                    >
                      Add
                    </button>
                  </div>

                  <div className="vendor-import-row">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".csv"
                      style={{ display: "none" }}
                      onChange={handleCsvImport}
                    />
                    <button
                      className="action-btn"
                      disabled={csvPreviewing}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      {csvPreviewing ? "Previewing…" : "Import CSV"}
                    </button>
                    <span className="vendor-import-hint">
                      CSV with vendor_name column (max 500 rows)
                    </span>
                  </div>

                  {csvPreview && (
                    <div className="csv-preview-panel">
                      <p className="csv-preview-summary">
                        <strong>CSV preview:</strong> {csvPreview.would_import} row
                        {csvPreview.would_import !== 1 ? "s" : ""} to import
                        {csvPreview.would_skip > 0
                          ? `, ${csvPreview.would_skip} in-file duplicate${csvPreview.would_skip !== 1 ? "s" : ""} skipped`
                          : ""}
                        {csvPreview.errors.length > 0
                          ? `, ${csvPreview.errors.length} error${csvPreview.errors.length !== 1 ? "s" : ""}`
                          : ""}
                      </p>
                      {csvPreview.errors.length > 0 && (
                        <ul className="csv-preview-errors">
                          {csvPreview.errors.slice(0, 5).map((e, i) => (
                            <li key={i}>{e}</li>
                          ))}
                          {csvPreview.errors.length > 5 && (
                            <li>…and {csvPreview.errors.length - 5} more</li>
                          )}
                        </ul>
                      )}
                      <div className="csv-preview-actions">
                        <button
                          className="action-btn"
                          disabled={csvPreview.would_import === 0}
                          onClick={handleCsvConfirm}
                        >
                          Confirm Import
                        </button>
                        <button className="action-btn-secondary" onClick={handleCsvCancel}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {vendorLoading ? (
                    <p className="settings-loading">Loading vendors...</p>
                  ) : vendors.length === 0 ? (
                    <p className="vendor-empty">
                      No vendors added yet. Add your first vendor above or
                      import a CSV.
                    </p>
                  ) : (
                    <>
                      <table className="vendor-table">
                        <thead>
                          <tr>
                            <th>Vendor</th>
                            <th>Product</th>
                            <th>Added</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {vendors.map((v) => (
                            <tr key={v.id}>
                              <td>
                                {v.vendor_name}
                                <span className="matched-count-badge">
                                  {v.matched_kev_count} KEV
                                </span>
                              </td>
                              <td>{v.product_name || "-"}</td>
                              <td>
                                {new Date(v.created_at).toLocaleDateString()}
                              </td>
                              <td>
                                <button
                                  className="vendor-delete-btn"
                                  onClick={() => handleDeleteVendor(v.id)}
                                  title="Remove"
                                >
                                  &times;
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {vendorTotal > vendorPageSize && (
                        <div className="vendor-pagination">
                          <button
                            className="action-btn"
                            disabled={vendorPage <= 1}
                            onClick={() => setVendorPage((p) => p - 1)}
                          >
                            Previous
                          </button>
                          <span className="vendor-page-info">
                            Page {vendorPage} of{" "}
                            {Math.ceil(vendorTotal / vendorPageSize)}
                          </span>
                          <button
                            className="action-btn"
                            disabled={
                              vendorPage >=
                              Math.ceil(vendorTotal / vendorPageSize)
                            }
                            onClick={() => setVendorPage((p) => p + 1)}
                          >
                            Next
                          </button>
                        </div>
                      )}
                    </>
                  )}
                    </div>
                  )}
                </section>
              )}

              {profile.org_id && (
                <section id="section-domains" className="settings-section">
                  <button className="section-accordion-header" onClick={() => toggleSection('domains')} aria-expanded={openSections.domains}>
                    <div className="section-accordion-header-text">
                      <span className="section-accordion-title">Organization Domains</span>
                      <span className="section-accordion-desc">Track domains your organization owns or monitors.</span>
                    </div>
                    <span className={`section-accordion-chevron${openSections.domains ? ' open' : ''}`}>›</span>
                  </button>
                  {openSections.domains && (
                    <div className="section-accordion-body">
                      {domainMsg && (
                    <div className="settings-action-msg">{domainMsg}</div>
                  )}
                  {domainError && (
                    <div
                      className="settings-error"
                      style={{
                        whiteSpace: "pre-line",
                        marginBottom: "0.75rem",
                      }}
                    >
                      {domainError}
                    </div>
                  )}

                  <div className="vendor-add-form">
                    <div className="vendor-input-wrapper">
                      <input
                        type="text"
                        placeholder="example.com"
                        value={newDomain}
                        onChange={(e) => setNewDomain(e.target.value)}
                        onKeyDown={(e) =>
                          e.key === "Enter" && handleAddDomain()
                        }
                      />
                    </div>
                    <button
                      className="action-btn"
                      onClick={handleAddDomain}
                      disabled={!newDomain.trim()}
                    >
                      Add Domain
                    </button>
                  </div>

                  {domainLoading ? (
                    <p className="settings-loading">Loading domains...</p>
                  ) : domains.length === 0 ? (
                    <p className="vendor-empty">No domains added yet.</p>
                  ) : (
                    <>
                      <table className="vendor-table">
                        <thead>
                          <tr>
                            <th>Domain</th>
                            <th>Added</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {domains.map((d) => (
                            <tr key={d.id}>
                              <td>{d.domain_name}</td>
                              <td>
                                {new Date(d.created_at).toLocaleDateString()}
                              </td>
                              <td>
                                <button
                                  className="vendor-delete-btn"
                                  onClick={() => handleDeleteDomain(d.id)}
                                  title="Remove"
                                >
                                  &times;
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {domainTotal > domainPageSize && (
                        <div className="vendor-pagination">
                          <button
                            className="action-btn"
                            disabled={domainPage <= 1}
                            onClick={() => setDomainPage((p) => p - 1)}
                          >
                            Previous
                          </button>
                          <span className="vendor-page-info">
                            Page {domainPage} of{" "}
                            {Math.ceil(domainTotal / domainPageSize)}
                          </span>
                          <button
                            className="action-btn"
                            disabled={
                              domainPage >=
                              Math.ceil(domainTotal / domainPageSize)
                            }
                            onClick={() => setDomainPage((p) => p + 1)}
                          >
                            Next
                          </button>
                        </div>
                      )}
                    </>
                  )}
                    </div>
                  )}
                </section>
              )}

              {profile.org_id && (
                <section id="section-uploads" className="settings-section">
                  <button className="section-accordion-header" onClick={() => toggleSection('uploads')} aria-expanded={openSections.uploads}>
                    <div className="section-accordion-header-text">
                      <span className="section-accordion-title">File Uploads</span>
                      <span className="section-accordion-desc">Upload files for your organization (CSV, PDF, TXT, JSON — max 10 MB).</span>
                    </div>
                    <span className={`section-accordion-chevron${openSections.uploads ? ' open' : ''}`}>›</span>
                  </button>
                  {openSections.uploads && (
                    <div className="section-accordion-body">
                      {uploadMsg && (
                    <div className="settings-action-msg">{uploadMsg}</div>
                  )}
                  {uploadError && (
                    <div
                      className="settings-error"
                      style={{
                        whiteSpace: "pre-line",
                        marginBottom: "0.75rem",
                      }}
                    >
                      {uploadError}
                    </div>
                  )}

                  <div className="vendor-import-row">
                    <input
                      ref={uploadFileInputRef}
                      type="file"
                      accept=".csv,.pdf,.txt,.json"
                      style={{ display: "none" }}
                      onChange={handleFileUpload}
                    />
                    <button
                      className="action-btn"
                      onClick={() => uploadFileInputRef.current?.click()}
                    >
                      Upload File
                    </button>
                    <span className="vendor-import-hint">
                      Accepted: CSV, PDF, TXT, JSON (max 10 MB)
                    </span>
                  </div>

                  {uploadLoading ? (
                    <p className="settings-loading">Loading uploads...</p>
                  ) : uploads.length === 0 ? (
                    <p className="vendor-empty">No files uploaded yet.</p>
                  ) : (
                    <>
                      <table className="vendor-table">
                        <thead>
                          <tr>
                            <th>Filename</th>
                            <th>Type</th>
                            <th>Size</th>
                            <th>Uploaded</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {uploads.map((u) => (
                            <tr key={u.id}>
                              <td>
                                <button
                                  className="vendor-delete-btn"
                                  style={{
                                    color: "#1565c0",
                                    textDecoration: "underline",
                                    cursor: "pointer",
                                    background: "none",
                                    border: "none",
                                    font: "inherit",
                                  }}
                                  onClick={() =>
                                    handleDownloadUpload(
                                      u.id,
                                      u.original_filename,
                                    )
                                  }
                                  title="Download"
                                >
                                  {u.original_filename}
                                </button>
                              </td>
                              <td>{u.content_type}</td>
                              <td>{formatFileSize(u.file_size_bytes)}</td>
                              <td>
                                {new Date(u.created_at).toLocaleDateString()}
                              </td>
                              <td>
                                <button
                                  className="vendor-delete-btn"
                                  onClick={() => handleDeleteUpload(u.id)}
                                  title="Delete"
                                >
                                  &times;
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {uploadTotal > 20 && (
                        <div className="vendor-pagination">
                          <button
                            className="action-btn"
                            disabled={uploadPage <= 1}
                            onClick={() => setUploadPage((p) => p - 1)}
                          >
                            Previous
                          </button>
                          <span className="vendor-page-info">
                            Page {uploadPage} of {Math.ceil(uploadTotal / 20)}
                          </span>
                          <button
                            className="action-btn"
                            disabled={uploadPage >= Math.ceil(uploadTotal / 20)}
                            onClick={() => setUploadPage((p) => p + 1)}
                          >
                            Next
                          </button>
                        </div>
                      )}
                    </>
                  )}
                    </div>
                  )}
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
