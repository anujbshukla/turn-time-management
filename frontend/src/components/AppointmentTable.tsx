import type {
  AppointmentListItem,
  AppointmentPagination,
} from "../types/appointments";

type AppointmentTableProps = {
  appointments: AppointmentListItem[];
  pagination: AppointmentPagination;
  pageSize: number;
  loading: boolean;
  error: string | null;

  onPreviousPage: () => void;
  onNextPage: () => void;
  onPageSizeChange: (pageSize: number) => void;

  onAppointmentSelect: (
    appointment: AppointmentListItem,
  ) => void;

  selectedAppointmentId?: string;
};

export function AppointmentTable({
  appointments,
  pagination,
  pageSize,
  loading,
  error,
  onPreviousPage,
  onNextPage,
  onPageSizeChange,
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
            Ordered by operational priority
          </p>
        </div>

        <span className="appointment-total">
          {pagination.total_items} total
        </span>
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
                  <th>Appointment</th>
                  <th>Customer</th>
                  <th>Facility</th>
                  <th>Carrier</th>
                  <th>Scheduled</th>
                  <th>Status</th>
                  <th>Risk</th>
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
                          event.key ===
                          "Enter" ||
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
                        {appointment.customer_name ??
                          "—"}
                      </td>

                      <td>
                        {
                          appointment.facility_name
                        }
                      </td>

                      <td>
                        {appointment.carrier_name ??
                          "—"}
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
                          {appointment.turn_risk_score ??
                            "—"}
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
                  !pagination.has_previous ||
                  loading
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
                  !pagination.has_next ||
                  loading
                }
                onClick={onNextPage}
              >
                Next
              </button>

              <label className="page-size-control">
                <span>
                  Rows per page
                </span>

                <select
                  value={pageSize}
                  onChange={(event) =>
                    onPageSizeChange(
                      Number(
                        event.target.value,
                      ),
                    )
                  }
                >
                  {[10, 20, 30, 40, 50].map(
                    (size) => (
                      <option
                        key={size}
                        value={size}
                      >
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