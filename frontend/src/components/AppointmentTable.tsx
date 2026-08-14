import type {
  AppointmentListItem,
  AppointmentPagination,
  AppointmentSortField,
  SortDirection,
} from "../types/appointments";

type AppointmentTableProps = {
  appointments: AppointmentListItem[];
  pagination: AppointmentPagination;
  pageSize: number;
  sortBy?: AppointmentSortField;
  sortDirection?: SortDirection;
  loading: boolean;
  error: string | null;

  onPreviousPage: () => void;
  onNextPage: () => void;
  onPageSizeChange: (pageSize: number) => void;
  onSortChange: (field: AppointmentSortField) => void;
  onCreateAppointment: () => void;

  onAppointmentSelect: (
    appointment: AppointmentListItem,
  ) => void;

  selectedAppointmentId?: string;
};

type SortableHeaderProps = {
  field: AppointmentSortField;
  label: string;
  activeField?: AppointmentSortField;
  direction?: SortDirection;
  disabled: boolean;
  onSortChange: (field: AppointmentSortField) => void;
};

function SortableHeader({
  field,
  label,
  activeField,
  direction,
  disabled,
  onSortChange,
}: SortableHeaderProps) {
  const isActive = activeField === field;
  const ariaSort = !isActive
    ? "none"
    : direction === "asc"
      ? "ascending"
      : "descending";

  const nextAction = !isActive
    ? "Sort ascending"
    : direction === "asc"
      ? "Sort descending"
      : "Clear sorting";

  return (
    <th aria-sort={ariaSort}>
      <button
        type="button"
        className={
          isActive
            ? "appointment-sort-button active"
            : "appointment-sort-button"
        }
        disabled={disabled}
        title={`${nextAction} by ${label}`}
        onClick={() => onSortChange(field)}
      >
        <span>{label}</span>
        <span
          className="appointment-sort-indicator"
          aria-hidden="true"
        >
          {isActive
            ? direction === "asc"
              ? "↑"
              : "↓"
            : "↕"}
        </span>
      </button>
    </th>
  );
}

export function AppointmentTable({
  appointments,
  pagination,
  pageSize,
  sortBy,
  sortDirection,
  loading,
  error,
  onPreviousPage,
  onNextPage,
  onPageSizeChange,
  onSortChange,
  onCreateAppointment,
  onAppointmentSelect,
  selectedAppointmentId,
}: AppointmentTableProps) {
  const firstVisibleRow =
    pagination.total_items === 0
      ? 0
      : (pagination.page - 1) *
          pagination.page_size +
        1;

  const lastVisibleRow = Math.min(
    pagination.page * pagination.page_size,
    pagination.total_items,
  );

  return (
    <section className="panel appointment-panel">
      <div className="panel-header appointment-panel-header">
        <div>
          <h2>Live Appointment Queue</h2>
          <p>
            Click a column heading to sort the full queue
          </p>
        </div>

        <div className="appointment-header-actions">
          <span className="appointment-total">
            {pagination.total_items} total
          </span>
          <button type="button" className="primary-button appointment-create-button" onClick={onCreateAppointment}>
            + Create appointment
          </button>
        </div>
      </div>

      {error && (
        <div className="table-error">
          {error}
        </div>
      )}

      {loading ? (
        <div className="table-state">
          Loading appointments...
        </div>
      ) : (
        <>
          <div className="appointment-table-wrapper">
            <table className="appointment-table">
              <thead>
                <tr>
                  <SortableHeader
                    field="appt_id"
                    label="Appointment"
                    activeField={sortBy}
                    direction={sortDirection}
                    disabled={loading}
                    onSortChange={onSortChange}
                  />
                  <SortableHeader
                    field="customer_name"
                    label="Customer"
                    activeField={sortBy}
                    direction={sortDirection}
                    disabled={loading}
                    onSortChange={onSortChange}
                  />
                  <SortableHeader
                    field="facility_name"
                    label="Facility"
                    activeField={sortBy}
                    direction={sortDirection}
                    disabled={loading}
                    onSortChange={onSortChange}
                  />
                  <SortableHeader
                    field="carrier_name"
                    label="Carrier"
                    activeField={sortBy}
                    direction={sortDirection}
                    disabled={loading}
                    onSortChange={onSortChange}
                  />
                  <SortableHeader
                    field="scheduled_time"
                    label="Scheduled"
                    activeField={sortBy}
                    direction={sortDirection}
                    disabled={loading}
                    onSortChange={onSortChange}
                  />
                  <SortableHeader
                    field="status"
                    label="Status"
                    activeField={sortBy}
                    direction={sortDirection}
                    disabled={loading}
                    onSortChange={onSortChange}
                  />
                  <SortableHeader
                    field="turn_risk_score"
                    label="Risk"
                    activeField={sortBy}
                    direction={sortDirection}
                    disabled={loading}
                    onSortChange={onSortChange}
                  />
                </tr>
              </thead>

              <tbody>
                {appointments.map((appointment) => {
                  const riskScore =
                    appointment.turn_risk_score ?? 0;

                  const statusClass =
                    appointment.status
                      .toLowerCase()
                      .replaceAll(" ", "-");

                  const riskClass =
                    riskScore >= 80
                      ? "critical"
                      : riskScore >= 60
                        ? "high"
                        : riskScore >= 30
                          ? "medium"
                          : "low";

                  const isSelected =
                    selectedAppointmentId ===
                    appointment.appt_id;

                  return (
                    <tr
                      key={appointment.appt_id}
                      className={
                        isSelected
                          ? "appointment-row selected"
                          : "appointment-row"
                      }
                      tabIndex={0}
                      role="button"
                      onClick={() =>
                        onAppointmentSelect(
                          appointment,
                        )
                      }
                      onKeyDown={(event) => {
                        if (
                          event.key === "Enter" ||
                          event.key === " "
                        ) {
                          event.preventDefault();
                          onAppointmentSelect(
                            appointment,
                          );
                        }
                      }}
                    >
                      <td className="appointment-id">
                        {appointment.appt_id}
                      </td>
                      <td>
                        {appointment.customer_name ?? "—"}
                      </td>
                      <td>{appointment.facility_name}</td>
                      <td>
                        {appointment.carrier_name ?? "—"}
                      </td>
                      <td>
                        {new Date(
                          appointment.scheduled_time,
                        ).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </td>
                      <td>
                        <span
                          className={`status-badge status-${statusClass}`}
                        >
                          {appointment.status}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`risk-badge ${riskClass}`}
                        >
                          {appointment.turn_risk_score ?? "—"}
                        </span>
                      </td>
                    </tr>
                  );
                })}

                {appointments.length === 0 && (
                  <tr>
                    <td
                      colSpan={7}
                      className="empty-table-cell"
                    >
                      No appointments found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="table-pagination">
            <div className="pagination-summary">
              {pagination.total_items === 0
                ? "Showing 0 appointments"
                : `Showing ${firstVisibleRow}–${lastVisibleRow} of ${pagination.total_items}`}
            </div>

            <div className="pagination-controls">
              <button
                type="button"
                disabled={
                  !pagination.has_previous || loading
                }
                onClick={onPreviousPage}
              >
                Previous
              </button>

              <span>
                Page {pagination.page} of{" "}
                {pagination.total_pages}
              </span>

              <button
                type="button"
                disabled={
                  !pagination.has_next || loading
                }
                onClick={onNextPage}
              >
                Next
              </button>

              <label className="page-size-control">
                <span>Rows per page</span>
                <select
                  value={pageSize}
                  onChange={(event) =>
                    onPageSizeChange(
                      Number(event.target.value),
                    )
                  }
                >
                  {[10, 20, 30, 40, 50].map(
                    (size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ),
                  )}
                </select>
              </label>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
