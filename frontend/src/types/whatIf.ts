export interface WhatIfRequest {
    selected_action_ids: number[];

    extra_loaders: number;

    extra_forklifts: number;

    pre_stage_products: boolean;
}

export interface WhatIfMetricSet {
    predicted_turn_time_minutes: number;

    sla_minutes: number;

    sla_miss_probability: number;

    turn_risk_score: number;

    detention_exposure: number;
}

export interface WhatIfScenario {
    projected_turn_time_minutes: number;

    minutes_saved: number;

    sla_recovered: boolean;

    projected_sla_miss_probability: number;

    projected_recovery_probability: number;

    projected_risk_score: number;

    action_cost: number;

    projected_detention_exposure: number;

    gross_savings: number;

    net_savings: number;
}

export interface WhatIfResponse {
    appt_id: string;

    selected_action_ids: number[];

    baseline: WhatIfMetricSet;

    scenario: WhatIfScenario;
}