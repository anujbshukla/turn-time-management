import type {
  AppointmentFilterReferenceData,
  AppointmentQuery,
  AppointmentReferenceData,
  CreateAppointmentPayload,
  CreateAppointmentResponse,
  PaginatedAppointmentsResponse,
  RescheduleAppointmentPayload,
  RescheduleAppointmentResponse,
  UpdateAppointmentPayload,
  UpdateAppointmentResponse,
} from "../types/appointments";

/* ----------------------------------------------------- */
/* Existing API model                                    */
/* ----------------------------------------------------- */

export interface AppointmentApiModel {
  appt_id: string;
  appt_date: string;
  customer_name: string | null;
  customer_id: string | null;
  facility_name: string | null;
  facility_id: string | null;
  scheduled_time: string;
  carrier_name: string | null;
  status: string | null;
}

/* ----------------------------------------------------- */
/* API configuration                                     */
/* ----------------------------------------------------- */

const API_BASE_URL = "http://127.0.0.1:8000";

/* ----------------------------------------------------- */
/* Existing endpoint                                     */
/* ----------------------------------------------------- */

export async function getAppointments(): Promise<
  AppointmentApiModel[]
> {
  const response = await fetch(
    `${API_BASE_URL}/api/appointments`,
  );

  if (!response.ok) {
    throw new Error(
      `Unable to load appointments: ${response.status}`,
    );
  }

  return response.json();
}

/* ----------------------------------------------------- */
/* Paginated endpoint                                    */
/* ----------------------------------------------------- */

export async function getPaginatedAppointments(
  query: AppointmentQuery,
): Promise<PaginatedAppointmentsResponse> {
  const params = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.pageSize),
  });

  if (query.facilityId) {
    params.set("facility_id", query.facilityId);
  }

  if (query.customerId) {
    params.set("customer_id", query.customerId);
  }

  if (query.carrierId) {
    params.set("carrier_id", query.carrierId);
  }

  if (query.dockId) {
    params.set("assigned_dock_id", query.dockId);
  }

  if (query.appointmentType) {
    params.set("appointment_type", query.appointmentType);
  }

  if (query.dateFrom) {
    params.set("date_from", query.dateFrom.split("T")[0]);
  }

  if (query.dateTo) {
    params.set("date_to", query.dateTo.split("T")[0]);
  }

  if (query.palletMin !== undefined) {
    params.set("pallet_min", String(query.palletMin));
  }

  if (query.palletMax !== undefined) {
    params.set("pallet_max", String(query.palletMax));
  }

  if (query.skuMin !== undefined) {
    params.set("sku_min", String(query.skuMin));
  }

  if (query.skuMax !== undefined) {
    params.set("sku_max", String(query.skuMax));
  }

  if (query.status) {
    params.set("status", query.status);
  }

  if (query.riskLevel) {
    params.set("risk_level", query.riskLevel);
  }

  if (query.outcome) {
    params.set("outcome", query.outcome);
  }

  if (query.search?.trim()) {
    params.set("search", query.search.trim());
  }

  if (query.sortBy && query.sortDirection) {
    params.set("sort_by", query.sortBy);
    params.set("sort_direction", query.sortDirection);
  }

  const response = await fetch(
    `${API_BASE_URL}/api/appointments/paged?${params.toString()}`,
  );

  if (!response.ok) {
    throw new Error(
      `Unable to load appointments: ${response.status}`,
    );
  }

  return response.json();
}

export async function getAppointmentReferenceData(): Promise<AppointmentReferenceData> {
  const response = await fetch(`${API_BASE_URL}/api/appointments/reference-data/options`);
  if (!response.ok) {
    throw new Error(`Unable to load appointment options: ${response.status}`);
  }
  return response.json();
}

export async function getAppointmentFilterOptions(
  query: Pick<
    AppointmentQuery,
    | "facilityId"
    | "customerId"
    | "carrierId"
    | "appointmentType"
    | "dateFrom"
    | "dateTo"
  >,
  signal?: AbortSignal,
): Promise<AppointmentFilterReferenceData> {
  const params = new URLSearchParams();
  if (query.facilityId) params.set("facility_id", query.facilityId);
  if (query.customerId) params.set("customer_id", query.customerId);
  if (query.carrierId) params.set("carrier_id", query.carrierId);
  if (query.appointmentType) params.set("appointment_type", query.appointmentType);
  if (query.dateFrom) params.set("date_from", query.dateFrom.split("T")[0]);
  if (query.dateTo) params.set("date_to", query.dateTo.split("T")[0]);

  const response = await fetch(
    `${API_BASE_URL}/api/appointments/reference-data/filter-options?${params.toString()}`,
    { signal },
  );
  if (!response.ok) {
    throw new Error(`Unable to load cascading filter options: ${response.status}`);
  }

  const payload = await response.json();
  return {
    facilities: payload.facilities ?? [],
    customers: payload.customers ?? [],
    carriers: payload.carriers ?? [],
    appointmentTypes: payload.appointment_types ?? [],
  };
}

export async function createAppointment(
  payload: CreateAppointmentPayload,
): Promise<CreateAppointmentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/appointments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const rawBody = await response.text();
    let message = `Unable to create appointment: ${response.status}`;

    if (rawBody) {
      try {
        const body = JSON.parse(rawBody);

        if (typeof body?.message === "string") {
          message = body.message;
        } else if (typeof body?.detail === "string") {
          message = body.detail;
        } else if (Array.isArray(body?.detail)) {
          message = body.detail
            .map((item: { loc?: unknown[]; msg?: string }) => {
              const location = item.loc?.slice(1).join(".") || "request";
              return `${location}: ${item.msg ?? "Invalid value"}`;
            })
            .join("; ");
        }
      } catch {
        message = rawBody;
      }
    }

    throw new Error(message);
  }

  return response.json();
}


export async function updateAppointment(
  appointmentId: string,
  payload: UpdateAppointmentPayload,
): Promise<UpdateAppointmentResponse> {
  const response = await fetch(`${API_BASE_URL}/api/appointments/${appointmentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const rawBody = await response.text();
    let message = `Unable to update appointment: ${response.status}`;
    if (rawBody) {
      try {
        const body = JSON.parse(rawBody);
        message = body?.message ?? body?.detail ?? message;
      } catch {
        message = rawBody;
      }
    }
    throw new Error(message);
  }
  return response.json();
}


export async function rescheduleAppointment(
  appointmentId: string,
  payload: RescheduleAppointmentPayload,
): Promise<RescheduleAppointmentResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/appointments/${appointmentId}/reschedule`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const rawBody = await response.text();
    let message = `Unable to reschedule appointment: ${response.status}`;
    if (rawBody) {
      try {
        const body = JSON.parse(rawBody);
        message = body?.message ?? body?.detail ?? message;
      } catch {
        message = rawBody;
      }
    }
    throw new Error(message);
  }

  return response.json();
}
