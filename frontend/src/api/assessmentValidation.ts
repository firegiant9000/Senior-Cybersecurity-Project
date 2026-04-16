/**
 * API client for the Assessment Validation endpoint.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export interface ValidationIssue {
  category: string;
  severity: "error" | "warning" | "info";
  field: string;
  message: string;
  suggestion: string | null;
}

export interface AssessmentValidation {
  issues: ValidationIssue[];
  score: number;
  passed: boolean;
  issue_counts: { error: number; warning: number; info: number };
}

export function fetchAssessmentValidation(
  signal: AbortSignal,
): Promise<AssessmentValidation> {
  return getJsonAuth<AssessmentValidation>(
    `${API_BASE_URL}/api/v1/organizations/mine/validation`,
    signal,
  );
}
