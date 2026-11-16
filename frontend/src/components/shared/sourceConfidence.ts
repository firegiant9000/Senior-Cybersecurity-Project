import type { SourceStatus } from "../../api/dataStatus";

// Least confident first. null (unknown) is below all of these.
const RANK: Record<SourceStatus, number> = {
  pending: 0,
  mocked: 1,
  static: 2,
  real: 3,
};

/** Lowest-confidence status; any unknown (null) makes the result unknown. */
export function leastConfident(statuses: (SourceStatus | null)[]): SourceStatus | null {
  let lowest: SourceStatus | null = null;
  for (const s of statuses) {
    if (s === null) return null;
    if (lowest === null || RANK[s] < RANK[lowest]) lowest = s;
  }
  return lowest;
}
