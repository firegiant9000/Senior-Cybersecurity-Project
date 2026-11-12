import { Link } from "react-router-dom";
import { isOrgAdmin } from "../utils/roleUtils";
import { useAccountProfile } from "./settings/useAccountProfile";
import AccountSection from "./settings/AccountSection";
import TeamSection from "./settings/TeamSection";
import AgentsSection from "./settings/AgentsSection";
import "../Dashboard.css";
import "./SettingsPage.css";

export default function SettingsPage() {
  const { profile, loading, error } = useAccountProfile();

  const canManageMembers =
    profile != null &&
    profile.org_id != null &&
    isOrgAdmin(profile.role, profile.org_role);

  return (
    <>
      <h1>Settings</h1>
      <nav className="settings-page-links" aria-label="Related pages">
        {profile?.org_id != null && <Link to="/org-profile">Organization Profile</Link>}
        {canManageMembers && <Link to="/settings/assessment-debug">Assessment Debug</Link>}
      </nav>

      <div className="settings-page settings-page--embedded">
        <div className="settings-card settings-card--wide">
          {loading && <p className="settings-loading">Loading profile...</p>}
          {error && <div className="settings-error">{error}</div>}

          {!loading && !error && profile && (
            <div className="settings-sections">
              <AccountSection profile={profile} />

              {profile.org_id != null && canManageMembers && (
                <TeamSection
                  orgId={profile.org_id}
                  userId={profile.id}
                  role={profile.role}
                  orgRole={profile.org_role}
                />
              )}
              {profile.org_id != null && canManageMembers && <AgentsSection />}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
