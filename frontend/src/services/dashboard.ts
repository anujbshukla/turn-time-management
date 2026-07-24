import type {
    DashboardResponse,
} from "../types/dashboard";

const API_BASE_URL = "http://127.0.0.1:8000";

export async function getDashboard(
    facilityId?: string,
): Promise<DashboardResponse> {
    const params = new URLSearchParams();

    if (facilityId) {
        params.set("facility_id", facilityId);
    }

    const queryString = params.toString();

    const response = await fetch(
        `${API_BASE_URL}/api/dashboard${queryString ? `?${queryString}` : ""
        }`,
    );

    if (!response.ok) {
        throw new Error(
            `Unable to load dashboard: ${response.status}`,
        );
    }

    return response.json();
}