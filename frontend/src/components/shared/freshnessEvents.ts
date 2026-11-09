export const FRESHNESS_REFRESH_EVENT = 'freshness:refresh';

export function requestFreshnessRefresh(): void {
  window.dispatchEvent(new Event(FRESHNESS_REFRESH_EVENT));
}
