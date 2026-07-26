import type {
    AppointmentDetailsResponse,
} from "../types/appointmentDetails";

const API_BASE_URL = "http://127.0.0.1:8000";

export async function getAppointmentDetails(
    appointmentId: string,
): Promise<AppointmentDetailsResponse> {
    const response = await fetch(
        `${API_BASE_URL}/api/appointments/${encodeURIComponent(
            appointmentId,
        )}/details`,
    );

    if (!response.ok) {
        throw new Error(
            `Unable to load appointment details: ${response.status}`,
        );
    }

    return response.json();
}