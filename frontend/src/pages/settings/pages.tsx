import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useUserContext } from '../../context/UserContext';
import { isOrgAdmin } from '../../utils/roleUtils';
import { useAccountProfile } from './useAccountProfile';
import AccountSection from './AccountSection';
import TeamSection from './TeamSection';
import AgentsSection from './AgentsSection';
import CompanySection from './CompanySection';
import SecurityProfileSection from './SecurityProfileSection';
import TechnologySection from './TechnologySection';
import DomainsSection from './DomainsSection';
import UploadsSection from './UploadsSection';
import AssessmentReadinessWidget from '../../components/AssessmentReadiness';
import ValidationPanel from '../../components/ValidationPanel';
import '../../Dashboard.css';
import '../SettingsPage.css';

const noop = () => {};
const ADMIN_ONLY_TEAM = 'Only organisation admins can manage the team.';
const ADMIN_ONLY_AGENTS = 'Only organisation admins can manage scanner agents.';

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="settings-page settings-page--embedded">
      <div className="settings-card settings-card--wide">
        <div className="settings-sections">{children}</div>
      </div>
    </div>
  );
}

function AdminOnly({ message }: { message: string }) {
  return (
    <Frame>
      <p>{message}</p>
    </Frame>
  );
}

function useSettingsAuth() {
  const { orgId, role, orgRole } = useAuth();
  return { orgId, canEdit: isOrgAdmin(role, orgRole) };
}

export function AccountPage() {
  const { profile, loading, error } = useAccountProfile();
  return (
    <div className="settings-page settings-page--embedded">
      <div className="settings-card settings-card--wide">
        {loading && <p className="settings-loading">Loading profile...</p>}
        {error && <div className="settings-error">{error}</div>}
        {!loading && !error && profile && (
          <div className="settings-sections">
            <AccountSection profile={profile} />
          </div>
        )}
      </div>
    </div>
  );
}

export function OrganisationPage() {
  const { orgId, canEdit } = useSettingsAuth();
  const { organization, refreshOrganization } = useUserContext();
  const location = useLocation();
  const scrolledKey = useRef<string | null>(null);

  // The intake wizard writes through PUT without notifying UserContext, so the cached
  // org can be stale; refresh on mount so the form reflects the server state.
  useEffect(() => {
    void refreshOrganization();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Bumped on any save so the readiness widget re-fetches.
  const [readinessKey, setReadinessKey] = useState(0);
  const bump = useCallback(() => setReadinessKey((k) => k + 1), []);

  // location.key changes on every navigation (even to the same URL), so a Fix click re-scrolls;
  // `organization` lets a cold load scroll once the section mounts. scrolledKey stops a save
  // (which replaces `organization`) from scrolling the page again within the same navigation.
  useEffect(() => {
    if (location.hash !== '#security-profile' || scrolledKey.current === location.key) return;
    const target = document.getElementById('security-profile');
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    scrolledKey.current = location.key;
  }, [location.hash, location.key, organization]);

  if (orgId == null) return null;

  return (
    <Frame>
      <AssessmentReadinessWidget refreshKey={readinessKey} />
      <ValidationPanel />
      <section className="settings-section">
        <h2>Company profile</h2>
        <CompanySection orgId={orgId} canEdit={canEdit} onChanged={bump} />
      </section>
      {canEdit && organization && (
        <section id="security-profile" className="settings-section">
          <h2>Security Profile</h2>
          <SecurityProfileSection
            orgId={orgId}
            canEdit={canEdit}
            onChanged={bump}
            onVendorsSynced={noop}
          />
        </section>
      )}
    </Frame>
  );
}

export function TechnologyPage() {
  const { orgId, canEdit } = useSettingsAuth();
  if (orgId == null) return null;
  return (
    <Frame>
      <section className="settings-section">
        <h2>Your Technology Stack</h2>
        <TechnologySection orgId={orgId} canEdit={canEdit} onChanged={noop} reloadKey={0} />
      </section>
    </Frame>
  );
}

export function DomainsPage() {
  const { orgId, canEdit } = useSettingsAuth();
  if (orgId == null) return null;
  return (
    <Frame>
      <section className="settings-section">
        <h2>Organization Domains</h2>
        <DomainsSection open orgId={orgId} canEdit={canEdit} onChanged={noop} />
      </section>
    </Frame>
  );
}

export function UploadsPage() {
  const { orgId, canEdit } = useSettingsAuth();
  if (orgId == null) return null;
  return (
    <Frame>
      <section className="settings-section">
        <h2>File Uploads</h2>
        <UploadsSection open orgId={orgId} canEdit={canEdit} onChanged={noop} />
      </section>
    </Frame>
  );
}

// Only admins fetch the account profile: userId (backend id) comes from it, and the
// profile request is not needed for members who cannot see TeamSection.
function TeamAdmin({
  orgId,
  role,
  orgRole,
}: {
  orgId: number;
  role: string | null;
  orgRole: string | null;
}) {
  const { profile, loading, error } = useAccountProfile();
  return (
    <>
      {loading && <p className="settings-loading">Loading profile...</p>}
      {error && <div className="settings-error">{error}</div>}
      {!loading && !error && profile && (
        <TeamSection orgId={orgId} userId={profile.id} role={role} orgRole={orgRole} />
      )}
    </>
  );
}

export function TeamPage() {
  const { orgId, role, orgRole } = useAuth();
  const canEdit = isOrgAdmin(role, orgRole);

  if (!canEdit) return <AdminOnly message={ADMIN_ONLY_TEAM} />;
  if (orgId == null) return null;
  return (
    <Frame>
      <TeamAdmin orgId={orgId} role={role} orgRole={orgRole} />
    </Frame>
  );
}

export function AgentsPage() {
  const { canEdit } = useSettingsAuth();
  if (!canEdit) return <AdminOnly message={ADMIN_ONLY_AGENTS} />;
  return (
    <Frame>
      <AgentsSection />
    </Frame>
  );
}
