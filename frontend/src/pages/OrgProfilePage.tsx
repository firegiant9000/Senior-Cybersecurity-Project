import { useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useUserContext } from "../context/UserContext";
import { API_BASE_URL, fetchWithAuth } from "../api/fetchWithAuth";
import { isOrgAdmin } from "../utils/roleUtils";
import DomainsSection from "./settings/DomainsSection";
import UploadsSection from "./settings/UploadsSection";
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

  // Bumped when cloud providers sync into vendors, so TechnologySection reloads page 1.
  const [vendorReloadKey, setVendorReloadKey] = useState(0);
  const bumpVendorReload = useCallback(() => setVendorReloadKey((k) => k + 1), []);

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
                  {/* Always mounted (state survives collapse); renders its body only while open. */}
                  <DomainsSection open={openSections.domains} orgId={profile.org_id} canEdit={canEditOrgProfile} onChanged={bumpReadiness} />
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
                  {/* Always mounted (state survives collapse); renders its body only while open. */}
                  <UploadsSection open={openSections.uploads} orgId={profile.org_id} canEdit={canEditOrgProfile} onChanged={bumpReadiness} />
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
