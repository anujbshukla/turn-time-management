export type DatePreset = "today" | "yesterday" | "tomorrow" | "next7" | "custom";
export type ComparisonMode = "none" | "same-day-last-week" | "week-over-week";

export interface OperationsFilters {
  facilityId?: string;
  customerId?: string;
  carrierId?: string;
  appointmentType?: "Inbound" | "Outbound";
  dateFrom: string;
  dateTo: string;
  datePreset: DatePreset;
}

export interface DashboardQueryFilters {
  facilityId?: string;
  customerId?: string;
  carrierId?: string;
  appointmentType?: "Inbound" | "Outbound";
  dateFrom?: string;
  dateTo?: string;
}
