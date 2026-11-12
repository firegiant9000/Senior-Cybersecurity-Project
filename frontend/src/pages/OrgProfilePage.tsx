import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useUserContext } from "../context/UserContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import { isOrgAdmin } from "../utils/roleUtils";
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
import CompanySection from "./settings/CompanySection";
import SecurityProfileSection from "./settings/SecurityProfileSection";
import TechnologySection from "./settings/TechnologySection";
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

export default function OrgProfilePage() {
  const { organization, refreshOrganization } = useUserContext();
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

  // UserContext caches the org from first load; the assessment intake wizard
  // writes through PUT but doesn't notify the context, so the cache can be
  // stale on first navigation here. Force a refresh on mount so the form
  // fields always reflect the latest server state.
  useEffect(() => {
    void refreshOrganization();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Bump to force the AssessmentReadinessWidget to re-fetch /mine/readiness
  // whenever a save happens on this page (org profile, security profile,
  // vendor add/remove, domain add/remove, CSV import).
  const [readinessKey, setReadinessKey] = useState(0);
  const bumpReadiness = useCallback(() => setReadinessKey((k) => k + 1), []);

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

  const uploadFileInputRef = useRef<HTMLInputElement>(null);

  // Bumped when cloud providers sync into vendors, so TechnologySection reloads page 1.
  const [vendorReloadKey, setVendorReloadKey] = useState(0);
  const bumpVendorReload = useCallback(() => setVendorReloadKey((k) => k + 1), []);

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
      bumpReadiness();
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
      bumpReadiness();
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
      bumpReadiness();
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
      bumpReadiness();
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

  const canEditOrgProfile =
    profile != null &&
    isOrgAdmin(profile.role, profile.org_role);
  const orgId = profile?.org_id ?? null;

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
              {profile.org_id != null && <AssessmentReadinessWidget refreshKey={readinessKey} />}
              {profile.org_id != null && <ValidationPanel />}

              {orgId != null && (
                <section className="settings-section">
                  <button className="section-accordion-header" onClick={() => toggleSection('company')} aria-expanded={openSections.company}>
                    <div className="section-accordion-header-text">
                      <span className="section-accordion-title">Company profile</span>
                      <span className="section-accordion-desc">Name, logo URL, and primary domain for your organization.</span>
                    </div>
                    <span className={`section-accordion-chevron${openSections.company ? ' open' : ''}`}>›</span>
                  </button>
                  {/* Kept mounted (hidden when collapsed) so drafts and banners survive collapse. */}
                  <div hidden={!openSections.company}>
                    <CompanySection orgId={orgId} canEdit={canEditOrgProfile} onChanged={bumpReadiness} />
                  </div>
                </section>
              )}

              {orgId != null && organization && canEditOrgProfile && (
                <section id="section-security-profile" className="settings-section">
                  <button className="section-accordion-header" onClick={() => toggleSection('security')} aria-expanded={openSections.security}>
                    <div className="section-accordion-header-text">
                      <span className="section-accordion-title">Security Profile</span>
                      <span className="section-accordion-desc">Security controls, compliance, data handling, and incident history.</span>
                    </div>
                    <span className={`section-accordion-chevron${openSections.security ? ' open' : ''}`}>›</span>
                  </button>
                  <div hidden={!openSections.security}>
                    <SecurityProfileSection orgId={orgId} canEdit={canEditOrgProfile} onChanged={bumpReadiness} onVendorsSynced={bumpVendorReload} />
                  </div>
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
                  {/* Kept mounted (hidden when collapsed) so drafts, paging and banners survive collapse. */}
                  <div hidden={!openSections.vendors}>
                    <TechnologySection orgId={profile.org_id} canEdit={canEditOrgProfile} onChanged={bumpReadiness} reloadKey={vendorReloadKey} />
                  </div>
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
