import type {
  DockStatus,
  KpiData,
  RecommendationData,
} from "../types/dashboard";

export const docks: DockStatus[] = [
  {
    name: "Dock 3",
    utilization: 92,
    status: "Needs attention",
  },
  {
    name: "Dock 5",
    utilization: 64,
    status: "Normal",
  },
  {
    name: "Dock 6",
    utilization: 38,
    status: "Available",
  },
  {
    name: "Dock 8",
    utilization: 81,
    status: "Busy",
  },
];

export const dashboardKpis: KpiData[] = [
  {
    label: "Turn Compliance",
    value: "92.5%",
    detail: "Target: 95%",
  },
  {
    label: "Appointments at Risk",
    value: "3",
    detail: "2 require action",
  },
  {
    label: "Predicted Misses",
    value: "1",
    detail: "Current shift",
  },
  {
    label: "Average Remaining SLA",
    value: "64 min",
    detail: "Active appointments",
  },
  {
    label: "Dock Utilization",
    value: "78.4%",
    detail: "1 dock needs attention",
  },
];

export const currentRecommendation: RecommendationData = {
  appointmentId: "APP100",
  summary:
    "APP100 has 60 minutes remaining and needs approximately 45 minutes to complete.",
  recommendedDock: "Dock 6",
  loadingSequence: "Move to position 1",
  additionalLabor: "1 loader",
  recoveryProbability: "91%",
  estimatedSavings: "$570",
};