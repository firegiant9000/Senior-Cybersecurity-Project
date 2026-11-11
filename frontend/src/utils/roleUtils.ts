import type { TabGroupDef } from '../config/tabGroups';

export function isPlatformAdmin(role: string | null | undefined): boolean {
  return role?.toLowerCase() === 'admin';
}

export function isOrgAdmin(
  role: string | null | undefined,
  orgRole: string | null | undefined,
): boolean {
  return isPlatformAdmin(role) || orgRole === 'admin' || orgRole === 'owner';
}

interface VisibilityContext {
  orgId: string | number | null;
  role: string | null;
  orgRole: string | null;
  orgLoading: boolean;
}

export function getVisibleGroups(
  groups: TabGroupDef[],
  ctx: VisibilityContext,
): TabGroupDef[] {
  const isAdmin = isPlatformAdmin(ctx.role);
  const hasOrg = !ctx.orgLoading && ctx.orgId != null;

  return groups
    .map((g): TabGroupDef | null => {
      if (g.requiresAdmin && !isAdmin) return null;

      if (g.requiresOrg && !hasOrg) return null;

      if (!g.subTabs) return g;
      const visibleSubs = g.subTabs.filter((s) => {
        if (s.requiresAdmin && !isAdmin) return false;
        if (s.requiresOrg && !hasOrg) return false;
        return true;
      });
      if (visibleSubs.length === 0) return null;
      return { ...g, subTabs: visibleSubs };
    })
    .filter((g): g is TabGroupDef => g !== null);
}
