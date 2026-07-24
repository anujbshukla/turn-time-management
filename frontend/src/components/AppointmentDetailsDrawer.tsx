import type {
    AppointmentListItem,
} from "../types/appointments";

type AppointmentDetailsDrawerProps = {
    appointment: AppointmentListItem | null;
    onClose: () => void;
};

function formatDate(value: string | null) {
    if (!value) {
        return "—";
    }

    return new Date(value).toLocaleString([], {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

export function AppointmentDetailsDrawer({
    appointment,
    onClose,
}: AppointmentDetailsDrawerProps) {
    if (!appointment) {
        return null;
    }

    const riskScore =
        appointment.turn_risk_score ?? 0;

    const riskLevel =
        riskScore >= 80
            ? "Critical"
            : riskScore >= 60
                ? "High"
                : riskScore >= 30
                    ? "Medium"
                    : "Low";

    return (
        <>
            <button
                type="button"
                className="drawer-backdrop"
                aria-label="Close appointment details"
                onClick={onClose}
            />

            <aside
                className="appointment-drawer"
                aria-label="Appointment details"
            >
                <div className="drawer-header">
                    <div>
                        <span className="drawer-eyebrow">
                            Appointment intelligence
                        </span>

                        <h2>{appointment.appt_id}</h2>

                        <p>
                            {appointment.customer_name ?? "Unknown customer"}
                        </p>
                    </div>

                    <button
                        type="button"
                        className="drawer-close"
                        onClick={onClose}
                        aria-label="Close"
                    >
                        ×
                    </button>
                </div>

                <div className="drawer-content">
                    <section className="drawer-section">
                        <div className="drawer-section-heading">
                            <h3>Operational status</h3>

                            <span
                                className={`risk-badge ${riskLevel.toLowerCase()}`}
                            >
                                {riskLevel} · {riskScore}
                            </span>
                        </div>

                        <div className="details-grid">
                            <div>
                                <span>Status</span>
                                <strong>{appointment.status}</strong>
                            </div>

                            <div>
                                <span>Facility</span>
                                <strong>
                                    {appointment.facility_name}
                                </strong>
                            </div>

                            <div>
                                <span>Carrier</span>
                                <strong>
                                    {appointment.carrier_name ?? "—"}
                                </strong>
                            </div>

                            <div>
                                <span>Dock</span>
                                <strong>
                                    {appointment.dock_name ??
                                        appointment.assigned_dock_id ??
                                        "Unassigned"}
                                </strong>
                            </div>
                        </div>
                    </section>

                    <section className="drawer-section">
                        <h3>Schedule</h3>

                        <div className="details-grid">
                            <div>
                                <span>Scheduled</span>
                                <strong>
                                    {formatDate(
                                        appointment.scheduled_time,
                                    )}
                                </strong>
                            </div>

                            <div>
                                <span>Estimated arrival</span>
                                <strong>
                                    {formatDate(
                                        appointment.estimated_arrival_time,
                                    )}
                                </strong>
                            </div>

                            <div>
                                <span>Arrival delay</span>
                                <strong>
                                    {appointment
                                        .actual_arrival_delay_minutes ??
                                        "—"}{" "}
                                    min
                                </strong>
                            </div>

                            <div>
                                <span>Predicted duration</span>
                                <strong>
                                    {appointment
                                        .predicted_duration_minutes ??
                                        "—"}{" "}
                                    min
                                </strong>
                            </div>
                        </div>
                    </section>

                    <section className="drawer-section">
                        <h3>Load</h3>

                        <div className="details-grid">
                            <div>
                                <span>Pallets</span>
                                <strong>
                                    {appointment.pallet_count}
                                </strong>
                            </div>

                            <div>
                                <span>SKUs</span>
                                <strong>
                                    {appointment.sku_count}
                                </strong>
                            </div>

                            <div>
                                <span>SLA</span>
                                <strong>
                                    {appointment.sla_minutes} min
                                </strong>
                            </div>

                            <div>
                                <span>Recovery probability</span>
                                <strong>
                                    {appointment
                                        .sla_recovery_probability ==
                                        null
                                        ? "—"
                                        : `${Math.round(
                                            appointment
                                                .sla_recovery_probability *
                                            100,
                                        )}%`}
                                </strong>
                            </div>
                        </div>
                    </section>

                    <section className="drawer-section recovery-section">
                        <span className="recommendation-label">
                            Recommended action
                        </span>

                        <p>
                            {appointment.recommended_action ??
                                "No recovery action has been generated."}
                        </p>

                        <div className="drawer-savings">
                            <span>Estimated savings</span>

                            <strong>
                                $
                                {(
                                    appointment.estimated_savings ?? 0
                                ).toLocaleString(undefined, {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2,
                                })}
                            </strong>
                        </div>
                    </section>
                </div>
            </aside>
        </>
    );
}