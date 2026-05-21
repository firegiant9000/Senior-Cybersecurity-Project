import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export type SourceStatus = "real" | "static" | "mocked" | "pending";

export interface DatasetStatus {
  key: string;
  label: string;
  status: SourceStatus;
  source: string;
  notes: string | null;
}

export interface DataStatusResponse {
  items: DatasetStatus[];
}

export async function fetchDataStatus(signal: AbortSignal): Promise<DataStatusResponse> {
  return getJsonAuth<DataStatusResponse>(
    `${API_BASE_URL}/api/v1/data-status`,
    signal,
  );
}
