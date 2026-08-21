export interface DockStatus {
  name: string;
  utilization: number;
  status: string;
}

export interface KpiData {
  label: string;
  value: string;
  detail: string;
}

export interface RecommendationData {
  appointmentId: string;
  summary: string;
  recommendedDock: string;
  loadingSequence: string;
  additionalLabor: string;
  recoveryProbability: string;
  estimatedSavings: string;
}
/* ==========================================================
   Dashboard API Response Models
========================================================== */

export interface DashboardSummary {
  total_appointments: number;
  in_progress: number;
  completed: number;
  late_arrivals: number;
  sla_misses: number;
  late_turned_on_time: number;
  late_recovered_with_recommendations: number;
  late_recovered_without_recommendations: number;
  average_turn_time_minutes: number | null;
  detention_exposure: number;
  recovery_contribution_percent: number;
}

export interface StatusDistributionItem {
  status: string;
  appointment_count: number;
}

export interface LateAppointmentOutcome {
  outcome: string;
  appointment_count: number;
}

export interface FacilityPerformanceItem {
  facility_id: string;
  facility_name: string;
  completed_appointments: number;
  on_time_turns: number;
  missed_turns: number;
  turn_compliance_percent: number | null;
}

export interface RiskDistributionItem {
  risk_level: string;
  appointment_count: number;
}

export interface DailyComplianceTrendItem {
  operation_date: string;
  completed_appointments: number;
  turn_compliance_percent: number | null;
}

export interface HighRiskAppointment {
  appt_id: string;
  customer_name: string | null;
  facility_name: string;
  carrier_name: string | null;
  dock_name: string | null;
  status: string;
  scheduled_time: string;
  estimated_arrival_time: string | null;
  actual_arrival_delay_minutes: number | null;
  pallet_count: number;
  sku_count: number;
  predicted_duration_minutes: number | null;
  turn_risk_score: number;
  sla_recovery_probability: number | null;
  predicted_missed: boolean;
  recommended_action: string | null;
  estimated_savings: number | null;
}

export interface DelaySlaReasonItem {
  reason: string;
  late_appointments: number;
  sla_misses: number;
  late_share_percent: number | null;
  average_delay_minutes: number | null;
  most_affected_dock: string | null;
}

export interface RecoveryPlanPerformanceItem {
  action_code: string;
  recovery_plan: string;
  times_used: number;
  acceptance_rate: number | null;
  sla_recoveries: number;
  success_rate: number | null;
  average_minutes_saved: number | null;
  net_savings: number;
}

export interface RecommendationSavings {
  without_recommendations: number;
  detention_with_recommendations: number;
  action_cost: number;
  gross_savings: number;
  net_savings: number;
  with_recommendations: number;
  roi: number;
  cost_reduction_percent: number;
  projected_gross_savings?: number;
  projected_action_cost?: number;
  accepted_gross_savings?: number;
  realized_gross_savings?: number;
  opportunity_appointments?: number;
  value_basis?: "projected_ml_opportunity" | "what_if_scenario" | string;
}


export interface ExecutivePriority {
  appt_id: string | null;
  title: string;
  reason: string;
  risk_score: number;
  estimated_savings: number;
  severity: "Critical" | "High" | "Medium";
}

export interface ExecutiveIndicator {
  label: string;
  score: number;
}

export interface ExecutiveIntelligence {
  health_score: number;
  health_status: string;
  health_tone: "positive" | "stable" | "warning" | "critical";
  briefing: string;
  top_priorities: ExecutivePriority[];
  indicators: ExecutiveIndicator[];
  headline_metrics: {
    critical_appointments: number;
    predicted_sla_misses: number;
    net_ai_savings: number;
    detention_exposure: number;
  };
}


export type PredictionTrend = "up" | "down" | "stable";
export type PredictionTone = "positive" | "stable" | "warning" | "critical";

export interface PredictionItem {
  key: string;
  label: string;
  value: string;
  unit: string;
  confidence: number;
  trend: PredictionTrend;
  primary_factor: string;
  recommendation: string;
  tone: PredictionTone;
}

export interface RiskMatrixItem {
  risk_level: "Critical" | "High" | "Medium" | "Low";
  appointment_count: number;
  trend: PredictionTrend;
  recommendation: string;
}

export interface PredictionHistoryItem {
  timestamp: string;
  predicted_sla_misses: number;
  actual_sla_misses: number | null;
}

export interface PredictionCenterData {
  generated_at: string;
  forecast_window_minutes: number;
  narrative: string;
  predictions: PredictionItem[];
  risk_matrix: RiskMatrixItem[];
  history: PredictionHistoryItem[];
  headline: {
    predicted_sla_misses: number;
    recovery_probability: number;
    detention_cost_forecast: number;
    congestion_location: string;
  };
}


export interface OperationalAlert {
  alert_id: string;
  severity: "Info" | "Warning" | "High" | "Critical";
  category: string;
  title: string;
  description: string;
  status: "Active" | "Snoozed" | "Dismissed" | "Resolved";
  impacted_appointment_count: number;
  estimated_financial_exposure: number;
  generated_at: string;
  appointment_ids: string[];
  highest_priority_appointment_id: string | null;
  risk_level: string | null;
  recommended_action: string;
}

export interface AiMission {
  mission_id: string;
  database_mission_id?: number;
  facility_id?: string;
  facility_name?: string;
  window_start?: string;
  window_end?: string;
  severity: "Info" | "Warning" | "High" | "Critical";
  category: string;
  title: string;
  objective: string;
  status:
  | "Proposed"
  | "Accepted"
  | "In Progress"
  | "Completed"
  | "Dismissed";
  priority_score: number;
  impacted_appointment_count: number;
  appointment_ids: string[];
  primary_appointment_id: string | null;
  projected_minutes_saved: number;
  estimated_financial_benefit: number;
  recovery_probability: number;
  generated_at: string;
  recommended_actions: string[];
  source_alert_ids: string[];
  projected_sla_misses_before?: number;
  projected_sla_misses_after?: number;
  appointments_recovered?: number;
  resource_shortages?: string[];
  scenario_constraints?: OptimizationScenarioConstraints;
  resource_capacity?: {
    source?: string;
    hourly?: Array<{
      hour: string;
      loaders_available: number;
      forklifts_available: number;
      staging_available: number;
      loader_headroom: number;
      forklift_headroom: number;
      staging_headroom: number;
    }>;
  };
  dock_feasibility?: {
    active_docks: number;
    dock_moves: number;
    temperature_compatibility_enforced: boolean;
  };
}

export interface OptimizationScenarioConstraints {
  max_extra_loaders_per_hour: number | null;
  max_extra_forklifts_per_hour: number | null;
  max_staging_labor_per_hour: number | null;
  allow_dock_reassignment: boolean;
}

export interface OptimizationMissionScenarioRequest {
  facility_id: string;
  customer_id?: string;
  carrier_id?: string;
  appointment_type?: "Inbound" | "Outbound";
  date_from: string;
  date_to: string;
  max_missions: number;
  max_extra_loaders_per_hour: number | null;
  max_extra_forklifts_per_hour: number | null;
  max_staging_labor_per_hour: number | null;
  allow_dock_reassignment: boolean;
}

export interface OptimizationMissionScenarioResponse {
  optimizer_version: string;
  window_start: string;
  window_end: string;
  candidate_appointments: number;
  facility_count: number;
  scenario_constraints: OptimizationScenarioConstraints;
  missions: AiMission[];
}

export interface OptimizationMissionExecution {
  mission_id: string | number;
  database_mission_id?: number;
  facility_id: string;
  status:
  | "Proposed"
  | "Accepted"
  | "In Progress"
  | "Completed"
  | "Dismissed";
  accepted_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  projected_sla_misses_before?: number;
  projected_sla_misses_after?: number;
  estimated_net_savings?: number;
  realized_sla_misses?: number | null;
  realized_minutes_saved?: number | null;
  realized_net_savings?: number | null;
  outcome_sample_size?: number;
  outcome_captured_at?: string | null;
  appointment_plan?: Array<{
    appt_id: string;
    priority_order: number;
    baseline_risk_score: number;
    baseline_projected_turn_minutes: number;
    optimized_projected_turn_minutes: number;
    sla_recovered: boolean;
    actual_turn_minutes?: number | null;
    actual_sla_missed?: boolean | null;
    realized_minutes_saved?: number | null;
    realized_net_savings?: number | null;
    actions: Array<{
      mission_action_id: number;
      action_code: string;
      action_description: string;
      status: string;
    }>;
  }>;
}


export type IntelligentKpiDirection = "up" | "down" | "stable";
export type IntelligentKpiTone = "positive" | "negative" | "neutral";

export interface IntelligentKpi {
  key: string;
  label: string;
  detail: string;
  format: "number" | "currency" | "percent";
  value: number;
  previous_value: number;
  delta_value: number;
  delta_percent: number;
  direction: IntelligentKpiDirection;
  tone: IntelligentKpiTone;
  rolling_average: number;
  trend: number[];
  trend_dates?: string[];
  target: number | null;
  forecast: number;
  forecast_confidence: number;
  explanation: string;
}


export type OperationsFeedCategory =
  | "AI Decisions"
  | "Operational Changes"
  | "Appointments"
  | "Alerts"
  | "Missions";

export interface OperationsFeedItem {
  feed_id: string;
  category: OperationsFeedCategory;
  event_type: string;
  title: string;
  description: string;
  occurred_at: string;
  appointment_id: string | null;
  facility_name: string | null;
  severity: "Info" | "Warning" | "High" | "Critical";
  actor: string | null;
  old_value: string | null;
  new_value: string | null;
  details: Record<string, unknown>;
  action: "open_appointment" | "filter_queue" | "run_what_if" | "none";
}


export type WarehouseHeatmapHealth = "Healthy" | "Watch" | "High" | "Critical" | "Inactive";
export type WarehouseHeatmapLayer = "risk" | "utilization" | "queue" | "sla" | "detention" | "recovery";

export interface WarehouseHeatmapFacility {
  facility_id: string;
  facility_name: string;
  dock_count: number;
  critical_docks: number;
  high_docks: number;
  average_utilization: number;
  risk_score: number;
  health: WarehouseHeatmapHealth;
  detention_exposure: number;
}

export interface WarehouseHeatmapDock {
  dock_id: string;
  dock_name: string;
  facility_id: string;
  facility_name: string;
  dock_type: string;
  temperature_zone: string | null;
  active: boolean;
  zone: string;
  sequence: number;
  health: WarehouseHeatmapHealth;
  risk_score: number;
  utilization_percent: number;
  queue_length: number;
  active_appointments: number;
  in_progress_appointments: number;
  average_delay_minutes: number;
  sla_risk_count: number;
  detention_exposure: number;
  recovery_opportunity: number;
  predicted_congestion: boolean;
  highest_risk_appointment_id: string | null;
  recommended_action: string;
}

export interface WarehouseHeatmapLegendItem {
  health: "Healthy" | "Watch" | "High" | "Critical";
  minimum: number;
  maximum: number;
}

export interface WarehouseHeatmapData {
  generated_at: string;
  facilities: WarehouseHeatmapFacility[];
  docks: WarehouseHeatmapDock[];
  legend: WarehouseHeatmapLegendItem[];
}


export interface PredictiveTimelineEvent {
  event_id: string;
  event_type: "APPOINTMENT_SURGE" | "SLA_RISK_WINDOW" | "DOCK_CONGESTION" | "DETENTION_EXPOSURE";
  forecast_time: string;
  severity: "Info" | "Warning" | "High" | "Critical";
  priority_score: number;
  title: string;
  description: string;
  facility_id: string | null;
  facility_name: string | null;
  dock_name: string | null;
  impacted_appointment_count: number;
  appointment_ids: string[];
  primary_appointment_id: string | null;
  detention_exposure: number;
  recommended_action: string;
  confidence: number;
}

export interface PredictiveTimelineData {
  generated_at: string;
  horizon_hours: number;
  facility_id: string | null;
  summary: {
    forecast_events: number;
    critical_events: number;
    high_events: number;
    detention_exposure: number;
    appointments_in_window: number;
  };
  events: PredictiveTimelineEvent[];
}

export interface DashboardResponse {
  summary: DashboardSummary;
  status_distribution: StatusDistributionItem[];
  late_appointment_outcomes: LateAppointmentOutcome[];
  facility_performance: FacilityPerformanceItem[];
  risk_distribution: RiskDistributionItem[];
  daily_compliance_trend: DailyComplianceTrendItem[];
  delay_sla_reasons: DelaySlaReasonItem[];
  recovery_plan_performance: RecoveryPlanPerformanceItem[];
  recommendation_savings: RecommendationSavings;
  high_risk_appointments: HighRiskAppointment[];
  executive_intelligence: ExecutiveIntelligence;
  prediction_center: PredictionCenterData;
  operational_alerts: OperationalAlert[];
  ai_missions: AiMission[];
  intelligent_kpis: IntelligentKpi[];
  operations_feed: OperationsFeedItem[];
  warehouse_heatmap: WarehouseHeatmapData;
  predictive_timeline: PredictiveTimelineData;
}
export interface DashboardWhatIfRequest {
  extra_loaders: number;
  extra_forklifts: number;
  pre_stage_products: boolean;
  facility_id?: string;
  customer_id?: string;
  carrier_id?: string;
  appointment_type?: "Inbound" | "Outbound";
  date_from?: string;
  date_to?: string;
  booking_draft?: GlobalCopilotBookingDraft | null;
}

export interface DashboardWhatIfMetrics {
  predicted_sla_misses: number;
  late_turns_recovered: number;
  detention_exposure: number;
}

export interface DashboardWhatIfScenario extends DashboardWhatIfMetrics {
  additional_recoveries: number;
  appointments_impacted: number;
  total_minutes_saved: number;
  gross_savings: number;
  action_cost: number;
  net_savings: number;
}

export interface DashboardWhatIfResponse {
  active: boolean;
  inputs: DashboardWhatIfRequest;
  scope: {
    candidate_appointments: number;
    operating_window_only: boolean;
  };
  baseline: DashboardWhatIfMetrics;
  scenario: DashboardWhatIfScenario;
  assumptions: string[];
  dashboard_patch: {
    summary: Partial<DashboardSummary>;
    late_appointment_outcomes: LateAppointmentOutcome[];
    risk_distribution: RiskDistributionItem[];
    recommendation_savings: RecommendationSavings;
  };
}

export type GlobalCopilotActionType =
  | "answer"
  | "filter_appointments"
  | "open_appointment"
  | "run_what_if"
  | "book_appointment";

export interface GlobalCopilotBookingProduct {
  product_id: string;
  quantity: number;
  product_label?: string | null;
  sku?: string | null;
}

export interface GlobalCopilotBookingDraft {
  customer_id?: string | null;
  customer_label?: string | null;
  carrier_id?: string | null;
  carrier_label?: string | null;
  facility_id?: string | null;
  facility_label?: string | null;
  assigned_dock_id?: string | null;
  assigned_dock_label?: string | null;
  scheduled_time?: string | null;
  appointment_type?: "Inbound" | "Outbound" | null;
  load_type: string;
  priority: number;
  sla_minutes: number;
  detention_cost_per_hour: number;
  products: GlobalCopilotBookingProduct[];
  pending_product_id?: string | null;
  pending_product_label?: string | null;
  pending_product_sku?: string | null;
  pending_product_quantity?: number | null;
}

export interface GlobalCopilotConversationMessage {
  role: "user" | "assistant";
  content: string;
  canonical_query_state?: Record<string, unknown> | null;
}

export interface GlobalCopilotRequest {
  question: string;
  conversation_history: GlobalCopilotConversationMessage[];
  facility_id?: string;
  customer_id?: string;
  carrier_id?: string;
  appointment_type?: "Inbound" | "Outbound";
  status?: string;
  risk_level?: string;
  date_from?: string;
  date_to?: string;
  booking_draft?: GlobalCopilotBookingDraft | null;
}

export interface GlobalCopilotQuickAction {
  label: string;
  action: "ask" | "filter_appointments" | "open_appointment" | "run_what_if";
  prompt?: string | null;
  metadata: Record<string, string>;
}

export interface GlobalCopilotActionIntent {
  action: GlobalCopilotActionType;
  action_ids: number[];
  confirmation_required: boolean;
  response_message: string;
  metadata: Record<string, string>;
  booking_draft?: GlobalCopilotBookingDraft | null;
}

export interface GlobalCopilotFact {
  label: string;
  value: string;
}

export interface GlobalCopilotResponse {
  mode: "answer" | "action";
  answer: string;
  facts: GlobalCopilotFact[];
  suggested_questions: string[];
  quick_actions: GlobalCopilotQuickAction[];
  action_intent: GlobalCopilotActionIntent | null;

  /**
   * Structured analytical state returned by the backend.
   *
   * This is stored with assistant messages and sent back through
   * conversation_history so follow-up questions can preserve the
   * previous metric, grouping, filters, time window and other
   * analytical context.
   */
  canonical_query_state?: Record<string, unknown> | null;
}


export interface MLMonitoringFeatureDrift {
  feature: string;
  recent_mean: number;
  prior_mean: number;
  standardized_shift: number;
  status: "Stable" | "Watch" | "High";
}

export interface MLFacilityPerformance {
  facility_id: string;
  facility_name: string;
  sample_size: number;
  duration_mae: number | null;
  sla_precision: number | null;
  sla_recall: number | null;
}

export interface MLMonitoringData {
  model_version: string;
  window_start: string;
  window_end: string;
  window_days: number;
  facility_id?: string | null;
  health_status: "Healthy" | "Watch" | "Retrain Recommended";
  retrain_recommended: boolean;
  reasons: string[];
  performance: {
    sample_size: number;
    duration_mae: number | null;
    duration_rmse: number | null;
    arrival_mae: number | null;
    true_positive: number;
    false_positive: number;
    false_negative: number;
    true_negative: number;
    sla_precision: number | null;
    sla_recall: number | null;
    sla_f2: number | null;
  };
  feature_drift: {
    score: number;
    features: MLMonitoringFeatureDrift[];
  };
  optimizer_effectiveness: {
    mission_count: number;
    appointment_sample_size: number;
    savings_error_percent: number | null;
    avg_realized_net_savings: number | null;
    avg_projected_net_savings: number | null;
  };
  facility_performance: MLFacilityPerformance[];
  governance_thresholds: Record<string, number>;
}
