export function isPlatformAdmin(role: string | null | undefined): boolean {
  return role?.toLowerCase() === 'admin';
}

export function isOrgAdmin(
  role: string | null | undefined,
  orgRole: string | null | undefined,
): boolean {
  return isPlatformAdmin(role) || orgRole === 'admin' || orgRole === 'owner';
}
