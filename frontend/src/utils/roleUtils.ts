export function canSeePipeline(role: string | null, orgRole: string | null): boolean {
  return role === 'admin' || orgRole === 'admin';
}
