/**
 * Activation analytics client (Month 2 Phase F4).
 *
 * Fire-and-forget POST. Failures are swallowed so a missing/slow
 * analytics endpoint never blocks the UX. Only non-PII metadata
 * should be passed in — the backend scrubs again as a safety net.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export type ActivationEventType =
  | "intake_step_skipped"
  | "csv_upload_started"
  | "csv_upload_completed"
  | "m365_connect_started"
  | "m365_connect_completed"
  | "dashboard_first_view";

export interface ActivationEventInput {
  event_type: ActivationEventType;
  org_id?: number | null;
  payload?: Record<string, unknown>;
}

export async function logActivationEvent(input: ActivationEventInput): Promise<void> {
  try {
    await fetchWithAuth(`${API_BASE_URL}/api/v1/analytics/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: input.event_type,
        org_id: input.org_id ?? null,
        payload: input.payload ?? null,
      }),
    });
  } catch {
    // Best-effort — analytics must never break the user flow.
  }
}
