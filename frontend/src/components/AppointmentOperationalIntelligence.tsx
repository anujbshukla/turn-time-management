import { useEffect, useMemo, useState } from "react";
import type {
    AppointmentDetailsAppointment,
    AppointmentPrediction,
    RecoverySummary,
} from "../types/appointmentDetails";

type Props = {
    appointment: AppointmentDetailsAppointment;
    prediction: AppointmentPrediction | null;
    recovery: RecoverySummary;
};

function formatDateTime(value: string | null | undefined) {
    if (!value) return "—";

    return new Date(value).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}

function formatTime(value: string | null | undefined) {
    if (!value) return "—";

    return new Date(value).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
    });
}

function formatDuration(milliseconds: number) {
    const sign = milliseconds < 0 ? "-" : "";
    const absolute = Math.abs(milliseconds);

    const hours = Math.floor(
        absolute / 3_600_000,
    );

    const minutes = Math.floor(
        (absolute % 3_600_000) / 60_000,
    );

    const seconds = Math.floor(
        (absolute % 60_000) / 1000,
    );

    return `${sign}${String(hours).padStart(2, "0")}:${String(
        minutes,
    ).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function calculateTurnTime(
    appointment: AppointmentDetailsAppointment,
) {
    if (!appointment.actual_loading_end_time) {
        return {
            value: "—",
            note:
                appointment.appointment_type === "Inbound"
                    ? "Available after unload ends"
                    : "Available after load ends",
            tone: "neutral",
        };
    }

    const appointmentTime =
        new Date(
            appointment.scheduled_time,
        ).getTime();

    const loadUnloadEnd =
        new Date(
            appointment.actual_loading_end_time,
        ).getTime();

    const elapsed =
        Math.abs(
            appointmentTime - loadUnloadEnd,
        );

    const slaMilliseconds =
        (appointment.sla_minutes ?? 120) *
        60_000;

    return {
        value: formatDuration(elapsed),
        note: "Appointment time → load/unload end",
        tone:
            elapsed <= slaMilliseconds
                ? "good"
                : "bad",
    };
}

function calculateRemainingTurnTime(
    appointment: AppointmentDetailsAppointment,
    now: number,
) {
    const loadingEnded =
        Boolean(
            appointment.actual_loading_end_time,
        ) ||
        appointment.status === "Completed";

    if (loadingEnded) {
        return {
            value: "—",
            note: "Load/unload completed",
            tone: "neutral",
        };
    }

    const deadline =
        new Date(
            appointment.scheduled_time,
        ).getTime() +
        (appointment.sla_minutes ?? 120) *
        60_000;

    const remaining =
        deadline - now;

    return {
        value: formatDuration(remaining),
        note:
            remaining >= 0
                ? "remaining to complete within SLA"
                : "past appointment SLA deadline",
        tone:
            remaining >= 15 * 60_000
                ? "good"
                : remaining >= 0
                    ? "warn"
                    : "bad",
    };
}

export function AppointmentOperationalIntelligence({
    appointment,
    prediction,
    recovery,
}: Props) {
    const [now, setNow] =
        useState(() => Date.now());

    const loadingEnded =
        Boolean(
            appointment.actual_loading_end_time,
        ) ||
        appointment.status === "Completed";

    useEffect(() => {
        if (loadingEnded) {
            return;
        }

        const timer =
            window.setInterval(
                () => setNow(Date.now()),
                1000,
            );

        return () =>
            window.clearInterval(timer);
    }, [loadingEnded]);

    const turnTime =
        useMemo(
            () =>
                calculateTurnTime(
                    appointment,
                ),
            [appointment],
        );

    const remainingTurnTime =
        useMemo(
            () =>
                calculateRemainingTurnTime(
                    appointment,
                    now,
                ),
            [appointment, now],
        );

    return (
        <div className="appointment-intelligence">
            <div className="turn-time-kpi-grid">
                <div
                    className={`live-sla-card ${turnTime.tone}`}
                >
                    <span>
                        Turn time
                    </span>

                    <strong>
                        {turnTime.value}
                    </strong>

                    <small>
                        {turnTime.note}
                    </small>
                </div>

                <div
                    className={`live-sla-card ${remainingTurnTime.tone}`}
                >
                    <span>
                        Remaining turn time
                    </span>

                    <strong>
                        {remainingTurnTime.value}
                    </strong>

                    <small>
                        {remainingTurnTime.note}
                    </small>
                </div>
            </div>

            <div className="operational-intelligence-grid">
                <div className="intelligence-card">
                    <span className="drawer-section-label">
                        Driver & equipment
                    </span>

                    <dl>
                        <div>
                            <dt>Driver</dt>
                            <dd>
                                {appointment.driver_name ?? "—"}
                            </dd>
                        </div>

                        <div>
                            <dt>License</dt>
                            <dd>
                                {appointment.license_number ?? "—"}
                            </dd>
                        </div>

                        <div>
                            <dt>License state</dt>
                            <dd>
                                {appointment.license_state ?? "—"}
                            </dd>
                        </div>

                        <div>
                            <dt>Phone</dt>
                            <dd>
                                {appointment.driver_phone ?? "—"}
                            </dd>
                        </div>

                        <div>
                            <dt>Tractor</dt>
                            <dd>
                                {appointment.tractor_number ?? "—"}
                            </dd>
                        </div>

                        <div>
                            <dt>Trailer</dt>
                            <dd>
                                {appointment.trailer_number ?? "—"}
                            </dd>
                        </div>
                    </dl>
                </div>

                <div className="intelligence-card">
                    <span className="drawer-section-label">
                        Route
                    </span>

                    <dl>
                        <div>
                            <dt>Origin</dt>
                            <dd>
                                {[
                                    appointment.origin_name,
                                    appointment.origin_city,
                                    appointment.origin_state,
                                ]
                                    .filter(Boolean)
                                    .join(" · ") || "—"}
                            </dd>
                        </div>

                        <div>
                            <dt>Destination</dt>
                            <dd>
                                {[
                                    appointment.destination_name,
                                    appointment.destination_city,
                                    appointment.destination_state,
                                ]
                                    .filter(Boolean)
                                    .join(" · ") || "—"}
                            </dd>
                        </div>
                    </dl>
                </div>
            </div>

            <div className="intelligence-card operational-snapshot-card">
                <span className="drawer-section-label">
                    Current operational status
                </span>

                <div className="details-grid">
                    <div>
                        <span>Status</span>
                        <strong>
                            {appointment.status ?? "—"}
                        </strong>
                    </div>
                    <div>
                        <span>Appointment type</span>
                        <strong>
                            {appointment.appointment_type ?? "—"}
                        </strong>
                    </div>
                    <div>
                        <span>Priority</span>
                        <strong>
                            {appointment.priority_tier ??
                                appointment.priority ??
                                "—"}
                        </strong>
                    </div>

                    <div>
                        <span>Facility</span>
                        <strong>
                            {appointment.facility_name ?? "—"}
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

                    <div>
                        <span>
                            Appointment time
                        </span>
                        <strong>
                            {formatTime(
                                appointment.scheduled_time,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>
                            Expected arrival
                        </span>
                        <strong>
                            {formatTime(
                                appointment.estimated_arrival_time,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>Carrier</span>
                        <strong>
                            {appointment.carrier_name ?? "—"}
                        </strong>
                    </div>

                    <div>
                        <span>Trailer</span>
                        <strong>
                            {appointment.trailer_number ?? "—"}
                        </strong>
                    </div>

                    <div>
                        <span>Pallets</span>
                        <strong>
                            {appointment.pallet_count ?? 0}
                        </strong>
                    </div>

                    <div>
                        <span>SKUs</span>
                        <strong>
                            {appointment.sku_count ?? 0}
                        </strong>
                    </div>

                    <div>
                        <span>
                            Total weight
                        </span>
                        <strong>
                            {appointment.total_weight != null
                                ? `${Math.round(
                                    appointment.total_weight,
                                ).toLocaleString()} lb`
                                : "—"}
                        </strong>
                    </div>
                </div>
            </div>

            <div className="intelligence-card timeline-card">
                <span className="drawer-section-label">
                    Operational timeline
                </span>

                <div className="operational-timeline-grid">
                    <div>
                        <span>Scheduled</span>
                        <strong>
                            {formatDateTime(
                                appointment.scheduled_time,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>Arrived</span>
                        <strong>
                            {formatDateTime(
                                appointment.actual_arrival_time,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>
                            {appointment.appointment_type ===
                                "Inbound"
                                ? "Unload start"
                                : "Load start"}
                        </span>

                        <strong>
                            {formatDateTime(
                                appointment.actual_loading_start_time,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>
                            {appointment.appointment_type ===
                                "Inbound"
                                ? "Unload end"
                                : "Load end"}
                        </span>

                        <strong>
                            {formatDateTime(
                                appointment.actual_loading_end_time,
                            )}
                        </strong>
                    </div>

                    <div>
                        <span>Dispatch</span>
                        <strong>
                            {formatDateTime(
                                appointment.actual_departure_time,
                            )}
                        </strong>
                    </div>
                </div>
            </div>

            <div className="intelligence-card sla-explanation-card">
                <div className="sla-explanation-heading">
                    <div>
                        <span className="drawer-section-label">
                            SLA outcome
                        </span>

                        <h4>
                            {recovery.sla_outcome_status}
                        </h4>
                    </div>

                    {prediction?.sla_miss_probability !=
                        null && (
                            <strong>
                                {Math.round(
                                    prediction.sla_miss_probability *
                                    100,
                                )}
                                % miss probability
                            </strong>
                        )}
                </div>

                <p>
                    {recovery.sla_outcome_reason}
                </p>

                {recovery.risk_contributors.length >
                    0 && (
                        <div className="risk-contributor-list">
                            <span className="drawer-section-label">
                                Why this probability?
                            </span>

                            {recovery.risk_contributors.map(
                                (item) => (
                                    <div
                                        key={item.label}
                                        className="risk-contributor-row"
                                    >
                                        <div>
                                            <strong>
                                                {item.label}
                                            </strong>

                                            <small>
                                                {item.reason}
                                            </small>
                                        </div>

                                        <span>
                                            +{item.impact_points} pts
                                        </span>
                                    </div>
                                ),
                            )}

                            <small className="explainability-note">
                                Operational contributors explain
                                the current risk context; they
                                are not SHAP/model attribution
                                values.
                            </small>
                        </div>
                    )}
            </div>
        </div>
    );
}