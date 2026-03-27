/**
 * Health check API client
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
}

export async function checkHealth(): Promise<HealthResponse> {
  return getJsonAuth<HealthResponse>(`${API_BASE_URL}/health`)
}

export async function checkHealthV1(): Promise<HealthResponse> {
  return getJsonAuth<HealthResponse>(`${API_BASE_URL}/api/v1/health`)
}
