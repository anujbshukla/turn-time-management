export type ActionDecisionStatus =
    | "Pending"
    | "Accepted"
    | "Rejected";

export type RecommendationActionDecision = {
    recommendation_action_id: number;
    decision_status: ActionDecisionStatus;
    notes?: string;
};

export type RecommendationDecisionRequest = {
    actions: RecommendationActionDecision[];
    decided_by: string;
};

export type RecommendationDecisionResponse = {
    recommendation_id: number;
    status:
    | "Pending"
    | "Partially Accepted"
    | "Accepted"
    | "Rejected";
    total_actions: number;
    accepted_actions: number;
    rejected_actions: number;
    pending_actions: number;
    accepted_minutes_saved: number;
    accepted_action_cost: number;
};

const API_BASE_URL = "http://127.0.0.1:8000";

export async function updateRecommendationDecisions(
    recommendationId: number,
    request: RecommendationDecisionRequest,
): Promise<RecommendationDecisionResponse> {
    const response = await fetch(
        `${API_BASE_URL}/api/recommendations/${recommendationId}/decisions`,
        {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(request),
        },
    );

    if (!response.ok) {
        const responseText = await response.text();

        throw new Error(
            responseText ||
            `Unable to update recovery actions: ${response.status}`,
        );
    }

    return response.json();
}