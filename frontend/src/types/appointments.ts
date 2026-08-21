export interface AppointmentListItem {
  appt_id: string;
  customer_name: string | null;
  customer_id: string | null;

  facility_id: string;
  facility_name: string;

  carrier_id: string | null;
  carrier_name: string | null;

  scheduled_time: string;

  estimated_arrival_time: string | null;
  actual_arrival_time: string | null;

  assigned_dock_id: string | null;
  dock_name: string | null;

  status: string;

  pallet_count: number;
  sku_count: number;

  priority: number;

  sla_minutes: number;

  actual_arrival_delay_minutes: number | null;

  predicted_duration_minutes: number | null;

  turn_risk_score: number | null;

  sla_recovery_probability: number | null;

  predicted_missed: boolean | null;

  recommended_action: string | null;

  estimated_savings: number | null;
}

export interface AppointmentPagination {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_previous: boolean;
  has_next: boolean;
}

export interface PaginatedAppointmentsResponse {
  items: AppointmentListItem[];
  pagination: AppointmentPagination;
}

export type AppointmentSortField =
  | "appt_id"
  | "customer_name"
  | "facility_name"
  | "carrier_name"
  | "scheduled_time"
  | "status"
  | "turn_risk_score";

export type SortDirection = "asc" | "desc";

export interface AppointmentQuery {
  page: number;
  pageSize: number;

  facilityId?: string;
  customerId?: string;
  carrierId?: string;
  dockId?: string;
  appointmentType?: "Inbound" | "Outbound";

  dateFrom?: string;
  dateTo?: string;

  palletMin?: number;
  palletMax?: number;
  skuMin?: number;
  skuMax?: number;

  status?: string;
  riskLevel?: string;
  outcome?: string;
  search?: string;

  sortBy?: AppointmentSortField;
  sortDirection?: SortDirection;
}

export type AppointmentFilters = {
  facilityId?: string;
  customerId?: string;
  carrierId?: string;
  dockId?: string;
  appointmentType?: "Inbound" | "Outbound";

  dateFrom?: string;
  dateTo?: string;

  palletMin?: number;
  palletMax?: number;
  skuMin?: number;
  skuMax?: number;

  status?: string;
  riskLevel?: string;
  outcome?: string;
  search?: string;
};

export interface AppointmentReferenceItem {
  id: string;
  label: string;
  facility_id: string | null;
}

export interface AppointmentProductReferenceItem {
  id: string;
  label: string;
  sku: string;
  category: string;
  unit_of_measure: string;
  unit_weight_lb: number;
  unit_volume_cuft: number;
  units_per_case: number;
  cases_per_pallet: number;
}

export interface AppointmentReferenceData {
  facilities: AppointmentReferenceItem[];
  customers: AppointmentReferenceItem[];
  carriers: AppointmentReferenceItem[];
  docks: AppointmentReferenceItem[];
  products: AppointmentProductReferenceItem[];
}

export interface AppointmentFilterReferenceData {
  facilities: AppointmentReferenceItem[];
  customers: AppointmentReferenceItem[];
  carriers: AppointmentReferenceItem[];
  appointmentTypes: AppointmentReferenceItem[];
}

export interface CreateAppointmentProductPayload {
  product_id: string;
  quantity: number;
}

export interface CreateAppointmentPayload {
  customer_id?: string | null;
  customer_name?: string | null;
  facility_id: string;
  carrier_id?: string | null;
  assigned_dock_id?: string | null;
  scheduled_time: string;
  estimated_arrival_time?: string | null;
  status: string;
  appointment_type?: string | null;
  load_type?: string | null;
  trailer_number?: string | null;
  pallet_count: number;
  sku_count: number;
  total_weight?: number | null;
  total_cube?: number | null;
  priority: number;
  sla_minutes: number;
  detention_cost_per_hour: number;
  distance_band?: string | null;
  traffic_severity: number;
  weather_severity: number;
  surge_indicator: boolean;
  products: CreateAppointmentProductPayload[];
}

export interface CreateAppointmentResponse {
  appt_id: string;
  appointment: Record<string, unknown>;
  prediction: Record<string, unknown> | null;
  scoring_status: "scored" | "model_unavailable" | "failed";
  message: string;
}

export interface UpdateAppointmentPayload {
  customer_id?: string | null;
  facility_id: string;
  carrier_id?: string | null;
  assigned_dock_id?: string | null;
  scheduled_time: string;
  estimated_arrival_time?: string | null;
  appointment_type: "Inbound" | "Outbound";
  load_type?: string | null;
  trailer_number?: string | null;
  priority: number;
  sla_minutes: number;
  detention_cost_per_hour: number;
  distance_band?: string | null;
  traffic_severity: number;
  weather_severity: number;
  surge_indicator: boolean;
  products: CreateAppointmentProductPayload[];
}

export interface UpdateAppointmentResponse
  extends CreateAppointmentResponse {
  changed_fields: string[];
}