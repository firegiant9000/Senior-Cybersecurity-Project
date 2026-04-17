import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";
import type { AssessmentIntakeResponse } from "./assessmentIntake";
import type { AssessmentValidation } from "./assessmentValidation";
import type { FindingsReport } from "./findings";

export interface FindingsReadinessBlock {
  ready: boolean;
  current_tier: string;
  blocking_reason: string | null;
  report: FindingsReport | null;
}

export interface DebugAssessmentResponse {
  generated_at: string;
  org_id: number;
  raw_profile: Record<string, unknown>;
  intake: AssessmentIntakeResponse;
  validation: AssessmentValidation;
  findings_readiness: FindingsReadinessBlock;
}

export function fetchAssessmentDebug(
  signal: AbortSignal,
): Promise<DebugAssessmentResponse> {
  return getJsonAuth<DebugAssessmentResponse>(
    `${API_BASE_URL}/api/v1/organizations/mine/debug`,
    signal,
  );
}
