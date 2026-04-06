import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { sendEmailVerification, sendPasswordResetEmail } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { useUserContext } from "../context/UserContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import { canEditOrganizationProfile } from "../components/ProtectedRoute";
import {
  OrgVendor,
  listVendors,
  createVendor,
  deleteVendor,
  importVendorsCsv,
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
import "../Dashboard.css";
import "./SettingsPage.css";

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

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { organization, refreshOrganization, loading: orgLoading, error: orgError } = useUserContext();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const [companyNameField, setCompanyNameField] = useState("");
  const [logoUrlField, setLogoUrlField] = useState("");
  const [primaryDomainField, setPrimaryDomainField] = useState("");
  const [companySaveMsg, setCompanySaveMsg] = useState("");
  const [companySaveErr, setCompanySaveErr] = useState("");
  const [companySaving, setCompanySaving] = useState(false);

  // Vendor / Tech Stack state
  const [vendors, setVendors] = useState<OrgVendor[]>([]);
  const [vendorTotal, setVendorTotal] = useState(0);
  const [vendorPage, setVendorPage] = useState(1);
  const [vendorLoading, setVendorLoading] = useState(false);
  const [vendorError, setVendorError] = useState("");
  const [vendorMsg, setVendorMsg] = useState("");
  const [newVendor, setNewVendor] = useState("");
  const [newProduct, setNewProduct] = useState("");
  const [vendorSuggestions, setVendorSuggestions] = useState<string[]>([]);
  const [productSuggestions, setProductSuggestions] = useState<string[]>([]);
  const [showVendorSuggestions, setShowVendorSuggestions] = useState(false);
  const [showProductSuggestions, setShowProductSuggestions] = useState(false);
  const vendorInputRef = useRef<HTMLInputElement>(null);
  const productInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadFileInputRef = useRef<HTMLInputElement>(null);
  const vendorPageSize = 20;

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

  const handleAddVendor = async () => {
    if (!profile?.org_id || !newVendor.trim()) return;
    setVendorError("");
    try {
      await createVendor(profile.org_id, newVendor.trim(), newProduct.trim());
      setNewVendor("");
      setNewProduct("");
      setVendorMsg("Vendor added");
      setVendorPage(1);
      loadVendors(profile.org_id, 1);
    } catch (err) {
      setVendorError(err instanceof Error ? err.message : "Failed to add vendor");
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
    try {
      const result = await importVendorsCsv(profile.org_id, file);
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
    }
    // Reset file input so same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = "";
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
    try {
      await addDomain(profile.org_id, newDomain.trim());
      setNewDomain("");
      setDomainMsg("Domain added");
      setDomainPage(1);
      loadDomains(profile.org_id, 1);
    } catch (err) {
      setDomainError(err instanceof Error ? err.message : "Failed to add domain");
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

  // Debounced autocomplete for vendor name
  useEffect(() => {
    if (newVendor.length < 2) { setVendorSuggestions([]); setShowVendorSuggestions(false); return; }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await autocompleteVendors(newVendor, "vendor");
        if (!cancelled) {
          setVendorSuggestions(results);
          setShowVendorSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) { setVendorSuggestions([]); setShowVendorSuggestions(false); }
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [newVendor]);

  // Debounced autocomplete for product name
  useEffect(() => {
    if (newProduct.length < 2) { setProductSuggestions([]); setShowProductSuggestions(false); return; }
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const results = await autocompleteVendors(newProduct, "product", newVendor || undefined);
        if (!cancelled) {
          setProductSuggestions(results);
          setShowProductSuggestions(results.length > 0);
        }
      } catch {
        if (!cancelled) { setProductSuggestions([]); setShowProductSuggestions(false); }
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [newProduct, newVendor]);

  // Sync company profile fields when organization data loads
  useEffect(() => {
    if (!organization) return;
    setCompanyNameField(organization.name);
    setLogoUrlField(organization.logo_url ?? "");
    setPrimaryDomainField(organization.primary_domain ?? "");
  }, [organization]);

  const canEditOrgProfile =
    profile != null && canEditOrganizationProfile(profile.role, profile.org_role);
  const companyFieldsDisabled = orgLoading || !organization || !canEditOrgProfile;

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
      };
      const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/organizations/${profile.org_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
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

  useEffect(() => {
    if (!organization) return;
    setCompanyNameField(organization.name);
    setLogoUrlField(organization.logo_url ?? "");
    setPrimaryDomainField(organization.primary_domain ?? "");
  }, [organization]);

  const canEditOrgProfile =
    profile != null && canEditOrganizationProfile(profile.role, profile.org_role);
  const companyFieldsDisabled = orgLoading || !organization || !canEditOrgProfile;

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
      };
      const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/organizations/${profile.org_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
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

  useEffect(() => {
    let cancelled = false;
    const loadProfile = async () => {
      try {
        const resp = await fetchWithAuth(`${API_BASE_URL}/api/v1/auth/me`);
        if (!resp.ok) throw new Error("Failed to load profile");
        const data: UserProfile = await resp.json();
        if (!cancelled) setProfile(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load profile");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadProfile();
    return () => { cancelled = true; };
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const handleResendVerification = async () => {
    setActionMsg("");
    try {
      if (auth.currentUser) {
        await sendEmailVerification(auth.currentUser);
        setActionMsg("Verification email sent! Check your inbox.");
      }
    } catch {
      setActionMsg("Failed to send verification email. Try again later.");
    }
  };

  const handlePasswordReset = async () => {
    setActionMsg("");
    try {
      if (user?.email) {
        await sendPasswordResetEmail(auth, user.email);
        setActionMsg("Password reset email sent! Check your inbox.");
      }
    } catch {
      setActionMsg("Failed to send password reset email. Try again later.");
    }
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Settings</h1>
        <div className="header-buttons">
          <button type="button" onClick={() => navigate("/")}>
            Back to Dashboard
          </button>
        </div>
      </header>

      <div className="settings-page settings-page--embedded">
        <div className="settings-card settings-card--wide">
        {loading && <p className="settings-loading">Loading profile...</p>}
        {error && <div className="settings-error">{error}</div>}

        {!loading && !error && profile && (
          <div className="settings-sections">
            {profile.org_id != null && (
              <section className="settings-section">
                <h2>Company profile</h2>
                <p className="tech-stack-description">
                  Name, logo URL, and primary domain for your organization. These align with dashboard branding where shown.
                </p>
                {!canEditOrgProfile && (
                  <p className="settings-readonly-hint">
                    Only organization owners, organization admins, or platform admins can edit these fields.
                  </p>
                )}
                {orgLoading && !organization && (
                  <p className="settings-loading">Loading organization…</p>
                )}
                {orgError && (
                  <div className="settings-error">Could not load organization profile.</div>
                )}
                {organization && (
                  <>
                    {companySaveMsg && <div className="settings-action-msg">{companySaveMsg}</div>}
                    {companySaveErr && (
                      <div className="settings-error" style={{ marginBottom: "0.75rem" }}>
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
                          placeholder="https://…"
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
                        onChange={(e) => setPrimaryDomainField(e.target.value)}
                        disabled={companyFieldsDisabled}
                        autoCapitalize="none"
                      />
                    </div>
                    {canEditOrgProfile && (
                      <div className="settings-actions" style={{ marginTop: "1rem" }}>
                        <button
                          type="button"
                          className="action-btn"
                          disabled={companySaving || !companyNameField.trim()}
                          onClick={() => void handleSaveCompanyProfile()}
                        >
                          {companySaving ? "Saving…" : "Save company profile"}
                        </button>
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            <section className="settings-section">
              <h2>Your account</h2>
              <div className="settings-field">
                <label>Email</label>
                <span>{profile.email}</span>
              </div>
              <div className="settings-field">
                <label>Role</label>
                <span className="role-badge">{profile.role}</span>
              </div>
              <div className="settings-field">
                <label>Auth Provider</label>
                <span>{profile.auth_provider}</span>
              </div>
              <div className="settings-field">
                <label>Account Created</label>
                <span>{new Date(profile.created_at).toLocaleDateString()}</span>
              </div>
              <div className="settings-field">
                <label>Status</label>
                <span className={`status-badge ${profile.is_active ? "active" : "inactive"}`}>
                  {profile.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </section>

            <section className="settings-section">
              <h2>Firebase Account</h2>
              <div className="settings-field">
                <label>Firebase UID</label>
                <span className="uid-text">{user?.uid}</span>
              </div>
              <div className="settings-field">
                <label>Email Verified</label>
                <span className={`status-badge ${user?.emailVerified ? "active" : "inactive"}`}>
                  {user?.emailVerified ? "Yes" : "No"}
                </span>
              </div>
              <div className="settings-field">
                <label>Last Sign-In</label>
                <span>{user?.metadata.lastSignInTime ?? "Unknown"}</span>
              </div>
            </section>

            <section className="settings-section">
              <h2>Actions</h2>
              {actionMsg && <div className="settings-action-msg">{actionMsg}</div>}
              <div className="settings-actions">
                {!user?.emailVerified && (
                  <button className="action-btn" onClick={handleResendVerification}>
                    Resend Verification Email
                  </button>
                )}
                <button className="action-btn" onClick={handlePasswordReset}>
                  Reset Password
                </button>
                <button className="logout-btn" onClick={handleLogout}>
                  Log Out
                </button>
              </div>
            </section>

            {profile.org_id && (
              <section className="settings-section">
                <h2>Your Technology Stack</h2>
                <p className="tech-stack-description">
                  Track the vendors and products your organization uses. We'll highlight relevant vulnerabilities from the KEV catalog.
                </p>

                {vendorMsg && <div className="settings-action-msg">{vendorMsg}</div>}
                {vendorError && <div className="settings-error" style={{ whiteSpace: "pre-line", marginBottom: "0.75rem" }}>{vendorError}</div>}

                {/* Add vendor form */}
                <div className="vendor-add-form">
                  <div className="vendor-input-wrapper">
                    <input
                      ref={vendorInputRef}
                      type="text"
                      placeholder="Vendor name"
                      value={newVendor}
                      onChange={(e) => setNewVendor(e.target.value)}
                      onFocus={() => vendorSuggestions.length > 0 && setShowVendorSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowVendorSuggestions(false), 200)}
                    />
                    {showVendorSuggestions && (
                      <ul className="autocomplete-dropdown">
                        {vendorSuggestions.map((s) => (
                          <li key={s} onMouseDown={() => { setNewVendor(s); setShowVendorSuggestions(false); }}>{s}</li>
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
                      onFocus={() => productSuggestions.length > 0 && setShowProductSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowProductSuggestions(false), 200)}
                    />
                    {showProductSuggestions && (
                      <ul className="autocomplete-dropdown">
                        {productSuggestions.map((s) => (
                          <li key={s} onMouseDown={() => { setNewProduct(s); setShowProductSuggestions(false); }}>{s}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <button className="action-btn" onClick={handleAddVendor} disabled={!newVendor.trim()}>
                    Add
                  </button>
                </div>

                {/* CSV import */}
                <div className="vendor-import-row">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    style={{ display: "none" }}
                    onChange={handleCsvImport}
                  />
                  <button className="action-btn" onClick={() => fileInputRef.current?.click()}>
                    Import CSV
                  </button>
                  <span className="vendor-import-hint">CSV with vendor_name column (max 500 rows)</span>
                </div>

                {/* Vendor table */}
                {vendorLoading ? (
                  <p className="settings-loading">Loading vendors...</p>
                ) : vendors.length === 0 ? (
                  <p className="vendor-empty">No vendors added yet. Add your first vendor above or import a CSV.</p>
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
                            <td>{new Date(v.created_at).toLocaleDateString()}</td>
                            <td>
                              <button className="vendor-delete-btn" onClick={() => handleDeleteVendor(v.id)} title="Remove">
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
                          Page {vendorPage} of {Math.ceil(vendorTotal / vendorPageSize)}
                        </span>
                        <button
                          className="action-btn"
                          disabled={vendorPage >= Math.ceil(vendorTotal / vendorPageSize)}
                          onClick={() => setVendorPage((p) => p + 1)}
                        >
                          Next
                        </button>
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            {profile.org_id && (
              <section className="settings-section">
                <h2>Organization Domains</h2>
                <p className="tech-stack-description">
                  Track domains your organization owns or monitors.
                </p>

                {domainMsg && <div className="settings-action-msg">{domainMsg}</div>}
                {domainError && <div className="settings-error" style={{ whiteSpace: "pre-line", marginBottom: "0.75rem" }}>{domainError}</div>}

                {/* Add domain form */}
                <div className="vendor-add-form">
                  <div className="vendor-input-wrapper">
                    <input
                      type="text"
                      placeholder="example.com"
                      value={newDomain}
                      onChange={(e) => setNewDomain(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleAddDomain()}
                    />
                  </div>
                  <button className="action-btn" onClick={handleAddDomain} disabled={!newDomain.trim()}>
                    Add Domain
                  </button>
                </div>

                {/* Domain table */}
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
                            <td>{new Date(d.created_at).toLocaleDateString()}</td>
                            <td>
                              <button className="vendor-delete-btn" onClick={() => handleDeleteDomain(d.id)} title="Remove">
                                &times;
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {domainTotal > domainPageSize && (
                      <div className="vendor-pagination">
                        <button className="action-btn" disabled={domainPage <= 1} onClick={() => setDomainPage((p) => p - 1)}>
                          Previous
                        </button>
                        <span className="vendor-page-info">
                          Page {domainPage} of {Math.ceil(domainTotal / domainPageSize)}
                        </span>
                        <button className="action-btn" disabled={domainPage >= Math.ceil(domainTotal / domainPageSize)} onClick={() => setDomainPage((p) => p + 1)}>
                          Next
                        </button>
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            {profile.org_id && (
              <section className="settings-section">
                <h2>File Uploads</h2>
                <p className="tech-stack-description">
                  Upload files for your organization (CSV, PDF, TXT, JSON — max 10 MB).
                </p>

                {uploadMsg && <div className="settings-action-msg">{uploadMsg}</div>}
                {uploadError && <div className="settings-error" style={{ whiteSpace: "pre-line", marginBottom: "0.75rem" }}>{uploadError}</div>}

                {/* Upload button */}
                <div className="vendor-import-row">
                  <input
                    ref={uploadFileInputRef}
                    type="file"
                    accept=".csv,.pdf,.txt,.json"
                    style={{ display: "none" }}
                    onChange={handleFileUpload}
                  />
                  <button className="action-btn" onClick={() => uploadFileInputRef.current?.click()}>
                    Upload File
                  </button>
                  <span className="vendor-import-hint">Accepted: CSV, PDF, TXT, JSON (max 10 MB)</span>
                </div>

                {/* Uploads table */}
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
                                style={{ color: "#1565c0", textDecoration: "underline", cursor: "pointer", background: "none", border: "none", font: "inherit" }}
                                onClick={() => handleDownloadUpload(u.id, u.original_filename)}
                                title="Download"
                              >
                                {u.original_filename}
                              </button>
                            </td>
                            <td>{u.content_type}</td>
                            <td>{formatFileSize(u.file_size_bytes)}</td>
                            <td>{new Date(u.created_at).toLocaleDateString()}</td>
                            <td>
                              <button className="vendor-delete-btn" onClick={() => handleDeleteUpload(u.id)} title="Delete">
                                &times;
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {uploadTotal > 20 && (
                      <div className="vendor-pagination">
                        <button className="action-btn" disabled={uploadPage <= 1} onClick={() => setUploadPage((p) => p - 1)}>
                          Previous
                        </button>
                        <span className="vendor-page-info">
                          Page {uploadPage} of {Math.ceil(uploadTotal / 20)}
                        </span>
                        <button className="action-btn" disabled={uploadPage >= Math.ceil(uploadTotal / 20)} onClick={() => setUploadPage((p) => p + 1)}>
                          Next
                        </button>
                      </div>
                    )}
                  </>
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
