import { describe, expect, it } from "vitest";
import { resolveLegacyUrl } from "./redirects";

// [pathname, search, hash, expected]
const rows: Array<[string, string, string, string | null]> = [
  ["/dashboard", "", "", "/overview"],
  ["/dashboard", "?tab=overview", "", "/overview"],
  ["/dashboard", "?tab=assessment", "", "/org/risk"],
  ["/dashboard", "?tab=assessment&sub=smbAdvisor", "", "/org/risk"],
  ["/dashboard", "?tab=smbAdvisor", "", "/org/risk"],
  ["/dashboard", "?tab=assessment&sub=nope", "", "/org/risk"],
  ["/dashboard", "?tab=assessment&sub=findings", "", "/org/findings"],
  ["/dashboard", "?tab=findings", "", "/org/findings"],
  ["/dashboard", "?tab=assessment&sub=aiSummary", "", "/org/briefing"],
  ["/dashboard", "?tab=aiSummary", "", "/org/briefing"],
  ["/dashboard", "?tab=vendorAlerts", "", "/org/vendor-alerts"],
  ["/dashboard", "?tab=assets", "", "/org/assets"],
  ["/dashboard", "?tab=threats", "", "/intel/vulnerabilities"],
  ["/dashboard", "?tab=threats&sub=threatIntel", "", "/intel/vulnerabilities"],
  ["/dashboard", "?tab=threatIntel", "", "/intel/vulnerabilities"],
  ["/dashboard", "?tab=threats&sub=nope", "", "/intel/vulnerabilities"],
  ["/dashboard", "?tab=threats&sub=riskScoring", "", "/intel/vulnerabilities?source=scored"],
  ["/dashboard", "?tab=riskScoring", "", "/intel/vulnerabilities?source=scored"],
  ["/dashboard", "?tab=threats&sub=anomalies", "", "/intel/anomalies/ic3"],
  ["/dashboard", "?tab=anomalies", "", "/intel/anomalies/ic3"],
  ["/dashboard", "?tab=trendsData", "", "/intel/trends"],
  ["/dashboard", "?tab=trendsData&sub=trends", "", "/intel/trends"],
  ["/dashboard", "?tab=trends", "", "/intel/trends"],
  ["/dashboard", "?tab=trendsData&sub=dataSources", "", "/intel/reference/ic3"],
  ["/dashboard", "?tab=dataSources", "", "/intel/reference/ic3"],
  ["/dashboard", "?tab=admin", "", "/admin/pipeline"],
  ["/dashboard", "?tab=admin&sub=pipelineHealth", "", "/admin/pipeline"],
  ["/dashboard", "?tab=pipelineHealth", "", "/admin/pipeline"],
  ["/dashboard", "?tab=admin&sub=normalizationLog", "", "/admin/normalization-log"],
  ["/dashboard", "?tab=normalizationLog", "", "/admin/normalization-log"],
  ["/dashboard", "?tab=nope&x=1", "", "/overview"],
  ["/assets", "", "", "/org/assets"],
  ["/inventory/upload", "", "", "/org/assets/upload"],
  ["/integrations", "", "", "/settings/integrations"],
  ["/integrations", "?code=abc&state=xyz", "", "/settings/integrations?code=abc&state=xyz"],
  ["/report/executive", "?autoprint=1", "", "/org/report?autoprint=1"],
  ["/settings", "", "", "/settings/account"],
  ["/settings/assessment-debug", "", "", "/admin/assessment-debug"],
  ["/org-profile", "", "", "/settings/organisation"],
  ["/org-profile", "", "#section-security-profile", "/settings/organisation#security-profile"],
  ["/org-profile", "", "#section-vendors", "/settings/technology"],
  ["/org-profile", "", "#section-domains", "/settings/domains"],
  ["/org-profile", "", "#section-uploads", "/settings/uploads"],
  ["/assessment-intake", "", "", "/onboarding"],
  ["/overview", "", "", null],
  ["/org/findings", "", "", null],
  ["/nope", "", "", null],
];

describe("resolveLegacyUrl", () => {
  it.each(rows)("%s%s%s maps to %s", (pathname, search, hash, expected) => {
    expect(resolveLegacyUrl(pathname, search, hash)).toBe(expected);
  });

  it("falls back to the group default for an unknown org-profile hash", () => {
    expect(resolveLegacyUrl("/org-profile", "", "#section-unknown")).toBe("/settings/organisation");
  });

  it("does not resolve inherited object keys as legacy tabs or subs", () => {
    expect(resolveLegacyUrl("/dashboard", "?tab=constructor", "")).toBe("/overview");
    expect(resolveLegacyUrl("/dashboard", "?tab=__proto__", "")).toBe("/overview");
    expect(resolveLegacyUrl("/dashboard", "?tab=threats&sub=constructor", "")).toBe("/intel/vulnerabilities");
    expect(resolveLegacyUrl("/constructor", "", "")).toBeNull();
  });
});
