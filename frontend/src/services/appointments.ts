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

const API_BASE_URL = "http://127.0.0.1:8000";

export async function getAppointments():
  Promise<AppointmentApiModel[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/appointments`
  );

  if (!response.ok) {
    throw new Error(
      `Unable to load appointments: ${response.status}`
    );
  }

  return response.json() as Promise<
    AppointmentApiModel[]
  >;
}