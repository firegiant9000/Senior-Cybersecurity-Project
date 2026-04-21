import type { TabGroupDef } from '../config/tabGroups';

export function canSeePipeline(role: string | null, orgRole: string | null): boolean {
  return role === 'admin' || orgRole === 'admin';
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
  const isAdmin = ctx.role === 'admin' || ctx.orgRole === 'admin';
  const hasOrg = !ctx.orgLoading && ctx.orgId != null;

  return groups
    .map((g): TabGroupDef | null => {
      if (g.requiresAdmin && !isAdmin) return null;

      // requiresOrg groups are shown as locked (not hidden) so users know they exist
      if (g.requiresOrg && !hasOrg) return { ...g, locked: true };

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
