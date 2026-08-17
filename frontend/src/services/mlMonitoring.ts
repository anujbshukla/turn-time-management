import type { MLMonitoringData } from "../types/dashboard";

const API_BASE_URL = "http://127.0.0.1:8000";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : `ML monitoring request failed (${response.status})`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function getMLMonitoring(
  windowDays = 30,
  facilityId?: string,
  persist = true,
): Promise<MLMonitoringData> {
  const params = new URLSearchParams({
    window_days: String(windowDays),
    persist: String(persist),
  });
  if (facilityId) {
    params.set("facility_id", facilityId);
  }

  const response = await fetch(
    `${API_BASE_URL}/api/ml/monitoring?${params.toString()}`,
  );
  return readJson<MLMonitoringData>(response);
}
