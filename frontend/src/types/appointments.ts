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

export interface AppointmentQuery {
    page: number;
    pageSize: number;

    facilityId?: string;
    status?: string;
    riskLevel?: string;
    outcome?: string;
    search?: string;
}
export type AppointmentFilters = {
    facilityId?: string;
    status?: string;
    riskLevel?: string;
    outcome?: string;
    search?: string;
};