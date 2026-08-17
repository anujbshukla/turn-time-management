import type {
  AiMission,
  OptimizationMissionExecution,
  OptimizationMissionScenarioRequest,
  OptimizationMissionScenarioResponse,
  OptimizationScenarioConstraints,
} from "../types/dashboard";

const API_BASE_URL = "http://127.0.0.1:8000";

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : `Optimization request failed (${response.status})`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function acceptOptimizationMission(
  mission: AiMission,
  constraints?: OptimizationScenarioConstraints,
): Promise<OptimizationMissionExecution> {
  if (!mission.facility_id || !mission.window_start || !mission.window_end) {
    throw new Error("Mission operating-window context is incomplete.");
  }

  const response = await fetch(
    `${API_BASE_URL}/api/optimization/missions/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        facility_id: mission.facility_id,
        window_start: mission.window_start,
        window_end: mission.window_end,
        max_extra_loaders_per_hour:
          constraints?.max_extra_loaders_per_hour ?? null,
        max_extra_forklifts_per_hour:
          constraints?.max_extra_forklifts_per_hour ?? null,
        max_staging_labor_per_hour:
          constraints?.max_staging_labor_per_hour ?? null,
        allow_dock_reassignment:
          constraints?.allow_dock_reassignment ?? true,
      }),
    },
  );
  return readJson<OptimizationMissionExecution>(response);
}

export async function updateOptimizationMissionStatus(
  missionId: number,
  status: "In Progress" | "Completed" | "Dismissed",
): Promise<OptimizationMissionExecution> {
  const response = await fetch(
    `${API_BASE_URL}/api/optimization/missions/${missionId}/status`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    },
  );
  return readJson<OptimizationMissionExecution>(response);
}


export async function simulateOptimizationMission(
  request: OptimizationMissionScenarioRequest,
): Promise<OptimizationMissionScenarioResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/optimization/scenario`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
  return readJson<OptimizationMissionScenarioResponse>(response);
}


export async function refreshOptimizationMissionOutcomes(
  missionId: number,
): Promise<OptimizationMissionExecution> {
  const response = await fetch(
    `${API_BASE_URL}/api/optimization/missions/${missionId}/outcomes/refresh`,
    { method: "POST" },
  );
  return readJson<OptimizationMissionExecution>(response);
}
