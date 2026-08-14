export interface CopilotWhatIfContext {
    selected_action_ids: number[];
    extra_loaders: number;
    extra_forklifts: number;
    pre_stage_products: boolean;
}

export interface AppointmentCopilotRequest {
    question: string;

    what_if: CopilotWhatIfContext | null;

    conversation_history:
    CopilotConversationMessage[];
}
export type CopilotMessageRole =
    | "user"
    | "assistant";

export type CopilotActionType =
    | "answer"
    | "accept_actions"
    | "reject_actions"
    | "run_what_if"
    | "filter_appointments"
    | "open_appointment";

export interface CopilotActionIntent {
    action: CopilotActionType;

    action_ids: number[];

    confirmation_required: boolean;

    response_message: string;

    metadata: Record<string, string>;
}

export interface CopilotConversationMessage {
    role: CopilotMessageRole;
    content: string;
}
export interface CopilotFact {
    label: string;
    value: string;
}

export interface AppointmentCopilotResponse {
    appt_id: string;

    mode: "answer" | "action";

    answer: string;

    facts: CopilotFact[];

    suggested_questions: string[];

    action_intent: CopilotActionIntent | null;
}