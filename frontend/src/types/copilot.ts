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
    answer: string;
    facts: CopilotFact[];
    suggested_questions: string[];
}