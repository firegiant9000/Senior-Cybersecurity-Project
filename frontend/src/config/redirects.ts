// Maps legacy URLs to their new locations. Pure: no app imports, no side effects.
// Maps are used instead of plain objects so inherited keys (e.g. "constructor") never match.

type TabGroup = {
  fallback: string;
  subs: Map<string, string>;
};

// Legacy /dashboard?tab=<group>&sub=<sub>. An unknown or missing sub uses the group fallback.
const DASHBOARD_GROUPS = new Map<string, TabGroup>([
  [
    "assessment",
    {
      fallback: "/org/risk",
      subs: new Map([
        ["smbAdvisor", "/org/risk"],
        ["findings", "/org/findings"],
        ["aiSummary", "/org/briefing"],
      ]),
    },
  ],
  [
    "threats",
    {
      fallback: "/intel/vulnerabilities",
      subs: new Map([
        ["threatIntel", "/intel/vulnerabilities"],
        ["riskScoring", "/intel/vulnerabilities?source=scored"],
        ["anomalies", "/intel/anomalies/ic3"],
      ]),
    },
  ],
  [
    "trendsData",
    {
      fallback: "/intel/trends",
      subs: new Map([
        ["trends", "/intel/trends"],
        ["dataSources", "/intel/reference/ic3"],
      ]),
    },
  ],
  [
    "admin",
    {
      fallback: "/admin/pipeline",
      subs: new Map([
        ["pipelineHealth", "/admin/pipeline"],
        ["normalizationLog", "/admin/normalization-log"],
      ]),
    },
  ],
]);

// Legacy /dashboard?tab=<name> where <name> is a top-level tab or a sub used directly as tab.
// Anything not listed here (including unknown tabs) resolves to /overview.
const DASHBOARD_TABS = new Map<string, string>([
  ["overview", "/overview"],
  ["vendorAlerts", "/org/vendor-alerts"],
  ["assets", "/org/assets"],
  ["smbAdvisor", "/org/risk"],
  ["findings", "/org/findings"],
  ["aiSummary", "/org/briefing"],
  ["threatIntel", "/intel/vulnerabilities"],
  ["riskScoring", "/intel/vulnerabilities?source=scored"],
  ["anomalies", "/intel/anomalies/ic3"],
  ["trends", "/intel/trends"],
  ["dataSources", "/intel/reference/ic3"],
  ["pipelineHealth", "/admin/pipeline"],
  ["normalizationLog", "/admin/normalization-log"],
]);

// Legacy paths that map one-to-one, with no query carried over.
const PATH_TARGETS = new Map<string, string>([
  ["/assets", "/org/assets"],
  ["/inventory/upload", "/org/assets/upload"],
  ["/settings", "/settings/account"],
  ["/settings/assessment-debug", "/admin/assessment-debug"],
  ["/assessment-intake", "/onboarding"],
]);

// Legacy paths whose query string must be kept (the M365 callback and the print view need it).
const PATH_TARGETS_KEEP_SEARCH = new Map<string, string>([
  ["/integrations", "/settings/integrations"],
  ["/report/executive", "/org/report"],
]);

// Legacy /org-profile hash to the new location. Unknown or missing hashes use the organisation page.
const ORG_PROFILE_HASHES = new Map<string, string>([
  ["#section-security-profile", "/settings/organisation#security-profile"],
  ["#section-vendors", "/settings/technology"],
  ["#section-domains", "/settings/domains"],
  ["#section-uploads", "/settings/uploads"],
]);

function resolveDashboard(search: string): string {
  const params = new URLSearchParams(search);
  const tab = params.get("tab") ?? "";
  const sub = params.get("sub") ?? "";

  const group = DASHBOARD_GROUPS.get(tab);
  if (group) {
    return group.subs.get(sub) ?? group.fallback;
  }
  return DASHBOARD_TABS.get(tab) ?? "/overview";
}

/**
 * Returns the new URL for a legacy URL, or null when the pathname is not a legacy route.
 * Takes the three parts of window.location (or react-router useLocation) separately.
 */
export function resolveLegacyUrl(pathname: string, search: string, hash: string): string | null {
  if (pathname === "/dashboard") {
    return resolveDashboard(search);
  }
  if (pathname === "/org-profile") {
    return ORG_PROFILE_HASHES.get(hash) ?? "/settings/organisation";
  }
  const keepSearchTarget = PATH_TARGETS_KEEP_SEARCH.get(pathname);
  if (keepSearchTarget) {
    return `${keepSearchTarget}${search}`;
  }
  return PATH_TARGETS.get(pathname) ?? null;
}
