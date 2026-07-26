export interface AppointmentDetailsAppointment {
    appt_id: string;
    appt_date: string;
    customer_id: string | null;
    customer_name: string | null;
    customer_industry: string | null;
    priority_tier: string | null;
    annual_revenue: number | null;

    facility_id: string;
    facility_name: string;
    timezone: string;

    carrier_id: string | null;
    carrier_name: string | null;

    assigned_dock_id: string | null;
    dock_name: string | null;
    dock_type: string | null;
    dock_temperature_zone: string | null;

    scheduled_time: string;
    estimated_arrival_time: string | null;
    actual_arrival_time: string | null;
    actual_loading_start_time: string | null;
    actual_loading_end_time: string | null;
    actual_departure_time: string | null;

    status: string;
    appointment_type: string | null;
    load_type: string | null;
    trailer_number: string | null;

    pallet_count: number;
    sku_count: number;
    total_weight: number | null;
    total_cube: number | null;
    priority: number;
    sla_minutes: number;
    detention_cost_per_hour: number;

    actual_arrival_delay_minutes: number | null;
    actual_loading_duration_minutes: number | null;
    actual_turn_time_minutes: number | null;
    actual_sla_missed: boolean | null;

    distance_band: string | null;
    traffic_severity: number;
    weather_severity: number;
    surge_indicator: boolean;
}

export interface AppointmentProduct {
    product_id: string;
    sku: string;
    product_name: string;
    category: string;
    temperature_zone: string;
    handling_type: string;
    unit_of_measure: string;
    unit_weight_lb: number;
    length_in: number;
    width_in: number;
    height_in: number;
    unit_volume_cuft: number;
    quantity: number;
    case_count: number;
    pallet_count: number;
    line_weight_lb: number;
    line_volume_cuft: number;
}

export interface AppointmentEvent {
    event_id: number;
    event_type: string;
    event_time: string;
    notes: string | null;
}

export interface AppointmentPrediction {
    prediction_id: number;
    predicted_arrival_time: string | null;
    predicted_delay_minutes: number;
    predicted_duration_minutes: number;
    sla_miss_probability: number | null;
    sla_recovery_probability: number | null;
    turn_risk_score: number | null;
    predicted_missed: boolean;
    model_version: string | null;
    generated_at: string;
}

export interface AppointmentRecommendation {
    recommendation_id: number;
    recommendation_type: string;
    recommended_action: string;
    recommended_dock_id: string | null;
    recommended_sequence: number | null;
    additional_labor: number;
    estimated_loss_without_action: number;
    estimated_cost_of_action: number;
    estimated_savings: number;
    status: string;
    created_at: string;
    responded_at: string | null;
    responded_by: string | null;
}

export interface RecommendationAction {
    recommendation_action_id: number;
    sequence_number: number;
    action_code: string;
    action_title: string;
    action_description: string;
    owner_role: string | null;
    start_by: string | null;
    estimated_minutes_saved: number;
    additional_loaders: number;
    additional_forklifts: number;
    required_equipment_type: string | null;
    required_dock_id: string | null;
    estimated_action_cost: number;
    status: string;
    decision_status:
    | "Pending"
    | "Accepted"
    | "Rejected";

    decision_at: string | null;
    decision_by: string | null;
    decision_notes: string | null;
}

export interface RecoverySummary {
    predicted_turn_time_minutes: number | null;

    total_minutes_saved: number;
    projected_turn_time_minutes: number | null;
    sla_recovered: boolean;

    proposed_minutes_saved: number;
    accepted_minutes_saved: number;
    rejected_minutes_saved: number;
    pending_minutes_saved: number;

    accepted_action_cost: number;

    proposed_projected_turn_time_minutes:
    number | null;

    accepted_projected_turn_time_minutes:
    number | null;

    sla_minutes: number;

    proposed_sla_recovered: boolean;
    accepted_sla_recovered: boolean;
}

export interface AppointmentDetailsResponse {
    appointment: AppointmentDetailsAppointment;
    products: AppointmentProduct[];
    events: AppointmentEvent[];
    prediction: AppointmentPrediction | null;
    recommendation: AppointmentRecommendation | null;
    recommendation_actions: RecommendationAction[];
    recovery_summary: RecoverySummary;
}