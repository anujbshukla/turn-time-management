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

export interface DashboardResponse {
  summary: DashboardSummary;
  status_distribution: StatusDistributionItem[];
  late_appointment_outcomes: LateAppointmentOutcome[];
  facility_performance: FacilityPerformanceItem[];
  risk_distribution: RiskDistributionItem[];
  daily_compliance_trend: DailyComplianceTrendItem[];
  high_risk_appointments: HighRiskAppointment[];
}