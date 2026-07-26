import type {
    AppointmentCopilotRequest,
    AppointmentCopilotResponse,
} from "../types/copilot";

const API_BASE_URL =
    "http://127.0.0.1:8000";

export async function askAppointmentCopilot(
    appointmentId: string,
    request: AppointmentCopilotRequest,
): Promise<AppointmentCopilotResponse> {
    const response = await fetch(
        `${API_BASE_URL}/api/appointments/${encodeURIComponent(
            appointmentId,
        )}/copilot`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(request),
        },
    );

    if (!response.ok) {
        throw new Error(
            `Unable to ask Copilot: ${response.status}`,
        );
    }

    return response.json();
}