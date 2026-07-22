import type {
  AppointmentApiModel,
} from "../services/appointments";

interface AppointmentTableProps {
  appointments: AppointmentApiModel[];
  loading: boolean;
  error: string | null;
}

export function AppointmentTable({
  appointments,
  loading,
  error,
}: AppointmentTableProps) {
  return (
    <div className="panel appointments-panel">
      <div className="panel-header">
        <div>
          <h2>Live Appointment Queue</h2>
          <p>Ordered by operational priority</p>
        </div>

        <button className="secondary-button">
          View all
        </button>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Appointment</th>
              <th>Customer</th>
              <th>Customer ID</th>
              <th>Facility</th>
              <th>Scheduled</th>
              <th>Carrier</th>
              <th>Status</th>
            </tr>
          </thead>

          <tbody>
            {loading && (
              <tr>
                <td colSpan={7}>
                  Loading appointments...
                </td>
              </tr>
            )}

            {error && (
              <tr>
                <td colSpan={7}>
                  Failed to load appointments: {error}
                </td>
              </tr>
            )}

            {!loading &&
              !error &&
              appointments.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    No appointments found.
                  </td>
                </tr>
              )}

            {!loading &&
              !error &&
              appointments.map((appointment) => {
                const scheduledTime = new Date(
                  appointment.scheduled_time,
                ).toLocaleString([], {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                });

                return (
                  <tr key={appointment.appt_id}>
                    <td>
                      <strong>
                        {appointment.appt_id}
                      </strong>
                    </td>

                    <td>
                      {appointment.customer_name ??
                        "Unknown"}
                    </td>

                    <td>
                      {appointment.customer_id ?? "—"}
                    </td>

                    <td>
                      {appointment.facility_name ??
                        "Unknown"}
                    </td>

                    <td>{scheduledTime}</td>

                    <td>
                      {appointment.carrier_name ??
                        "Unknown"}
                    </td>

                    <td>
                      <span className="status-badge">
                        {appointment.status ??
                          "Unknown"}
                      </span>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}