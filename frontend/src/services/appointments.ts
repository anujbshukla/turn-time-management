import type {
  AppointmentQuery,
  PaginatedAppointmentsResponse,
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
    params.set(
      "facility_id",
      query.facilityId,
    );
  }

  if (query.status) {
    params.set(
      "status",
      query.status,
    );
  }

  if (query.riskLevel) {
    params.set(
      "risk_level",
      query.riskLevel,
    );
  }

  if (query.outcome) {
    params.set(
      "outcome",
      query.outcome,
    );
  }

  if (query.search?.trim()) {
    params.set(
      "search",
      query.search.trim(),
    );
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