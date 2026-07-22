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