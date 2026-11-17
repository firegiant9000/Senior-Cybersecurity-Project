/**
 * Helpers for a confirm dialog's `returnFocus` when the confirmed action
 * removes the row that held the trigger. Rows carry `data-row-id`, actions
 * carry `data-action`; callers name both explicitly.
 */

/** Ids after `removed` in list order, then ids before it, nearest first. */
export function neighbourIds<T extends string | number>(
  ids: readonly T[],
  removed: T,
): T[] {
  const i = ids.indexOf(removed);
  if (i === -1) return [];
  return [...ids.slice(i + 1), ...ids.slice(0, i).reverse()];
}

/**
 * The first enabled `[data-action=action]` control inside a
 * `[data-row-id]` row under `root`, trying `ids` in order.
 */
export function findRowAction(
  root: HTMLElement | null | undefined,
  ids: readonly (string | number)[],
  action: string,
): HTMLElement | null {
  if (!root) return null;
  const rows = new Map<string, Element>();
  root.querySelectorAll("[data-row-id]").forEach((row) => {
    const id = row.getAttribute("data-row-id");
    if (id !== null && !rows.has(id)) rows.set(id, row);
  });
  for (const id of ids) {
    const row = rows.get(String(id));
    if (!row) continue;
    for (const el of row.querySelectorAll<HTMLElement>("[data-action]")) {
      if (
        el.getAttribute("data-action") === action &&
        el.isConnected &&
        !el.matches(":disabled")
      ) {
        return el;
      }
    }
  }
  return null;
}
