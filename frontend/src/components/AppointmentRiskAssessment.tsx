import type {
  AppointmentDetailsAppointment,
  AppointmentPrediction,
  AppointmentRecommendation,
  RecoverySummary,
} from "../types/appointmentDetails";

type Props = {
  appointment: AppointmentDetailsAppointment;
  prediction: AppointmentPrediction | null;
  recovery: RecoverySummary;
  recommendation: AppointmentRecommendation | null;
  score: number;
};

function formatPercent(
  value: number | null | undefined,
) {
  if (value == null) return "—";
  return `${Math.round(value * 100)}%`;
}

function formatCurrency(
  value: number | null | undefined,
) {
  return `$${(value ?? 0).toLocaleString(
    "en-US",
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    },
  )}`;
}

export function AppointmentRiskAssessment({
  appointment,
  prediction,
  recovery,
  recommendation,
  score,
}: Props) {
  return (
    <>
      <section className="drawer-section risk-assessment-section">
        <span className="drawer-section-label">
          AI risk assessment
        </span>

        <div className="risk-assessment-grid">
          <div>
            <span>Risk score</span>
            <strong>
              {score}
              <small>/100</small>
            </strong>
          </div>

          <div>
            <span>SLA miss probability</span>
            <strong>
              {formatPercent(
                prediction?.sla_miss_probability,
              )}
            </strong>
          </div>

          <div>
            <span>Predicted turn</span>
            <strong>
              {recovery.predicted_turn_time_minutes ??
                "—"}
              <small> min</small>
            </strong>
          </div>

          <div>
            <span>Target SLA</span>
            <strong>
              {recovery.sla_minutes ??
                appointment.sla_minutes ??
                "—"}
              <small> min</small>
            </strong>
          </div>
        </div>

        <div className="comparison-grid">
          <div className="comparison-card">
            <span>Without recovery plan</span>
            <strong>
              {recovery.predicted_turn_time_minutes ??
                "—"}{" "}
              min
            </strong>
            <small>
              {prediction?.predicted_missed
                ? "SLA miss predicted"
                : "SLA currently achievable"}
            </small>
          </div>

          <div className="comparison-card recovered">
            <span>Full AI recovery plan</span>
            <strong>
              {recovery.proposed_projected_turn_time_minutes ??
                recovery.projected_turn_time_minutes ??
                "—"}{" "}
              min
            </strong>
            <small>
              {(recovery.proposed_sla_recovered ??
                recovery.sla_recovered ??
                false)
                ? "SLA recovered"
                : "Further action required"}
            </small>
          </div>
        </div>

        <div className="comparison-grid">
          <div className="comparison-card">
            <span>Currently accepted actions</span>
            <strong>
              {recovery.accepted_projected_turn_time_minutes ??
                recovery.predicted_turn_time_minutes ??
                "—"}{" "}
              min
            </strong>
            <small>
              {recovery.accepted_sla_recovered
                ? "Accepted actions recover SLA"
                : "Additional actions may be required"}
            </small>
          </div>

          <div className="comparison-card recovered">
            <span>Accepted minutes saved</span>
            <strong>
              {recovery.accepted_minutes_saved ?? 0}{" "}
              min
            </strong>
            <small>
              Based only on accepted actions
            </small>
          </div>
        </div>
      </section>

      <section className="drawer-section">
        <span className="drawer-section-label">
          Root causes
        </span>

        <h3>
          Why this appointment is at risk
        </h3>

        <ul className="root-cause-list">
          {(appointment.actual_arrival_delay_minutes ??
            prediction?.predicted_delay_minutes ??
            0) > 0 && (
            <li>
              Carrier is expected or recorded{" "}
              <strong>
                {appointment.actual_arrival_delay_minutes ??
                  prediction?.predicted_delay_minutes}{" "}
                minutes late
              </strong>
              .
            </li>
          )}

          {appointment.pallet_count >= 25 && (
            <li>
              High load volume of{" "}
              <strong>
                {appointment.pallet_count} pallets
              </strong>{" "}
              increases handling time.
            </li>
          )}

          {appointment.sku_count >= 7 && (
            <li>
              The appointment contains{" "}
              <strong>
                {appointment.sku_count} SKUs
              </strong>
              , increasing staging and verification
              effort.
            </li>
          )}

          {appointment.traffic_severity >= 3 && (
            <li>
              Traffic conditions are elevated at{" "}
              <strong>
                severity {appointment.traffic_severity}
              </strong>
              .
            </li>
          )}

          {appointment.weather_severity >= 3 && (
            <li>
              Weather conditions may affect arrival
              and handling operations.
            </li>
          )}

          {appointment.surge_indicator && (
            <li>
              The facility is operating under a
              surge-volume condition.
            </li>
          )}
        </ul>
      </section>

      <section className="drawer-section recovery-value-section">
        <span className="drawer-section-label">
          Financial impact
        </span>

        <div className="details-grid">
          <div>
            <span>Loss without action</span>
            <strong>
              {formatCurrency(
                recommendation
                  ?.estimated_loss_without_action,
              )}
            </strong>
          </div>

          <div>
            <span>Accepted action cost</span>
            <strong>
              {formatCurrency(
                recovery.accepted_action_cost ??
                  recommendation
                    ?.estimated_cost_of_action,
              )}
            </strong>
          </div>

          <div>
            <span>Estimated savings</span>
            <strong>
              {formatCurrency(
                recommendation?.estimated_savings,
              )}
            </strong>
          </div>

          <div>
            <span>Recovery probability</span>
            <strong>
              {formatPercent(
                prediction?.sla_recovery_probability,
              )}
            </strong>
          </div>
        </div>
      </section>
    </>
  );
}
