import type { AppointmentFilterReferenceData } from "../types/appointments";
import type {
  DashboardResponse,
  DelaySlaReasonItem,
  RecoveryPlanPerformanceItem,
} from "../types/dashboard";

const API_BASE_URL = "http://127.0.0.1:8000";

export interface DashboardFilters {
  facilityId?: string;
  customerId?: string;
  carrierId?: string;
  appointmentType?: "Inbound" | "Outbound";
  dateFrom?: string;
  dateTo?: string;
}

export interface DashboardIntelligenceResponse {
  delay_sla_reasons: DelaySlaReasonItem[];
  recovery_plan_performance: RecoveryPlanPerformanceItem[];
}


export async function getDashboardIntelligenceFilterOptions(
  filters: DashboardFilters = {},
): Promise<AppointmentFilterReferenceData> {
  const params = buildDashboardParams(filters);
  const queryString = params.toString();

  const response = await fetch(
    `${API_BASE_URL}/api/dashboard/intelligence/filter-options${queryString ? `?${queryString}` : ""}`,
  );

  if (!response.ok) {
    throw new Error(
      `Unable to load root-cause filter options: ${response.status}`,
    );
  }

  const payload = await response.json();
  return {
    facilities: payload.facilities ?? [],
    customers: payload.customers ?? [],
    carriers: payload.carriers ?? [],
    appointmentTypes: payload.appointment_types ?? [],
  };
}

function buildDashboardParams(filters: DashboardFilters = {}) {
  const params = new URLSearchParams();

  if (filters.facilityId) params.set("facility_id", filters.facilityId);
  if (filters.customerId) params.set("customer_id", filters.customerId);
  if (filters.carrierId) params.set("carrier_id", filters.carrierId);
  if (filters.appointmentType) {
    params.set("appointment_type", filters.appointmentType);
  }
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);

  return params;
}

export async function getDashboard(
  filters: DashboardFilters = {},
): Promise<DashboardResponse> {
  const params = buildDashboardParams(filters);
  const queryString = params.toString();

  const response = await fetch(
    `${API_BASE_URL}/api/dashboard${queryString ? `?${queryString}` : ""}`,
  );

  if (!response.ok) {
    throw new Error(`Unable to load dashboard: ${response.status}`);
  }

  return response.json();
}

export async function getDashboardIntelligence(
  filters: DashboardFilters = {},
): Promise<DashboardIntelligenceResponse> {
  const params = buildDashboardParams(filters);
  const queryString = params.toString();

  const response = await fetch(
    `${API_BASE_URL}/api/dashboard/intelligence${queryString ? `?${queryString}` : ""}`,
  );

  if (!response.ok) {
    throw new Error(
      `Unable to load root-cause intelligence: ${response.status}`,
    );
  }

  return response.json();
}

export async function runDashboardWhatIf(
  request: import("../types/dashboard").DashboardWhatIfRequest,
): Promise<import("../types/dashboard").DashboardWhatIfResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/dashboard/what-if`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    let message = "Unable to run dashboard What-If simulation";
    try {
      const payload = await response.json() as { message?: string; detail?: string };
      message = payload.message ?? payload.detail ?? message;
    } catch {
      // Preserve fallback.
    }
    throw new Error(message);
  }

  return response.json();
}

export async function askGlobalCopilot(
  request: import("../types/dashboard").GlobalCopilotRequest,
): Promise<import("../types/dashboard").GlobalCopilotResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/dashboard/copilot`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );

  if (!response.ok) {
    let message = "Unable to ask the Global AI Warehouse Copilot";
    try {
      const payload = await response.json() as {
        message?: string;
        detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
      };

      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail
          .map((item) => {
            const location = item.loc?.slice(1).join(".");
            return location
              ? `${location}: ${item.msg ?? "Invalid value"}`
              : item.msg ?? "Invalid value";
          })
          .join("; ");
      } else {
        message = payload.message ?? message;
      }
    } catch {
      // Keep fallback.
    }
    throw new Error(message);
  }

  return response.json();
}
