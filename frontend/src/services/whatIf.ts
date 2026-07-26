import type {
    WhatIfRequest,
    WhatIfResponse,
} from "../types/whatIf";

const API =
    "http://127.0.0.1:8000";

export async function runWhatIf(
    appointmentId: string,
    request: WhatIfRequest,
): Promise<WhatIfResponse> {
    const response = await fetch(
        `${API}/api/appointments/${appointmentId}/what-if`,
        {
            method: "POST",
            headers: {
                "Content-Type":
                    "application/json",
            },
            body: JSON.stringify(request),
        },
    );

    if (!response.ok) {
        throw new Error(
            "Unable to run What-If analysis",
        );
    }

    return response.json();
}