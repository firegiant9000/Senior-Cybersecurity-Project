/**
 * Health check API client
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`)
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`)
  }
  return response.json()
}

export async function checkHealthV1(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health`)
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`)
  }
  return response.json()
}
