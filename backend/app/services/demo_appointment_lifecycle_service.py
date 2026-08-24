from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DemoLifecycleResult:
    updated_appointments: int


class DemoAppointmentLifecycleService:
    """Advance DEMO appointments using the facility-local current time.

    The reconciliation is idempotent and only mutates DEMO appointments.
    Completed and Cancelled appointments are never reopened.

    Milestones:
    - arrival: existing actual arrival, else ETA, else scheduled time
    - load/unload start: max(arrival, scheduled) + 10 minutes
    - load/unload end: start + latest predicted duration (fallback 45 minutes)
    - dispatch: load/unload end + 10 minutes

    Status progression:
    Scheduled -> En Route -> Arrived -> In Progress -> Completed

    Turn time follows the application's current definition:
    abs(Appointment Time - Load/Unload End Time)
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def reconcile(self) -> DemoLifecycleResult:
        result = self.db.execute(
            text(
                """
                WITH latest_predictions AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.predicted_duration_minutes
                    FROM appointment_predictions AS prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                ),
                base AS (
                    SELECT
                        appointment.appt_id,
                        appointment.status,
                        appointment.scheduled_time,
                        appointment.estimated_arrival_time,
                        appointment.actual_arrival_time,
                        appointment.actual_start_time,
                        appointment.actual_end_time,
                        appointment.actual_loading_start_time,
                        appointment.actual_loading_end_time,
                        appointment.actual_departure_time,
                        appointment.actual_arrival_delay_minutes,
                        appointment.actual_loading_duration_minutes,
                        appointment.actual_turn_time_minutes,
                        appointment.actual_sla_missed,
                        appointment.sla_minutes,
                        appointment.updated_at,
                        (
                            CURRENT_TIMESTAMP AT TIME ZONE
                            COALESCE(
                                NULLIF(facility.timezone, ''),
                                'America/New_York'
                            )
                        ) AS local_now,
                        COALESCE(
                            appointment.actual_arrival_time,
                            appointment.estimated_arrival_time,
                            appointment.scheduled_time
                        ) AS arrival_candidate,
                        GREATEST(
                            COALESCE(
                                prediction.predicted_duration_minutes,
                                appointment.actual_loading_duration_minutes,
                                45
                            ),
                            5
                        )::INTEGER AS duration_minutes
                    FROM appointments AS appointment
                    JOIN facilities AS facility
                      ON facility.facility_id = appointment.facility_id
                    LEFT JOIN latest_predictions AS prediction
                      ON prediction.appt_id = appointment.appt_id
                    WHERE appointment.appt_id LIKE 'DEMO%'
                      AND appointment.status NOT IN (
                          'Completed',
                          'Cancelled'
                      )
                ),
                milestones AS (
                    SELECT
                        base.*,
                        GREATEST(
                            base.arrival_candidate,
                            base.scheduled_time
                        ) + INTERVAL '10 minutes'
                        AS start_candidate
                    FROM base
                ),
                calculated AS (
                    SELECT
                        milestones.*,
                        milestones.start_candidate
                        + (
                            milestones.duration_minutes
                            * INTERVAL '1 minute'
                        ) AS end_candidate
                    FROM milestones
                ),
                final_values AS (
                    SELECT
                        calculated.*,
                        calculated.end_candidate
                        + INTERVAL '10 minutes'
                        AS dispatch_candidate,
                        CASE
                            WHEN calculated.local_now
                                 >= calculated.end_candidate
                                THEN 'Completed'
                            WHEN calculated.local_now
                                 >= calculated.start_candidate
                                THEN 'In Progress'
                            WHEN calculated.local_now
                                 >= calculated.arrival_candidate
                                THEN 'Arrived'
                            WHEN calculated.local_now
                                 >= calculated.scheduled_time
                                    - INTERVAL '60 minutes'
                                THEN 'En Route'
                            ELSE 'Scheduled'
                        END AS derived_status
                    FROM calculated
                ),
                reconciled AS (
                    SELECT
                        final_values.*,
                        CASE
                            WHEN final_values.status = 'In Progress'
                                 AND final_values.derived_status IN (
                                     'Scheduled',
                                     'En Route',
                                     'Arrived'
                                 )
                                THEN 'In Progress'
                            WHEN final_values.status = 'Arrived'
                                 AND final_values.derived_status IN (
                                     'Scheduled',
                                     'En Route'
                                 )
                                THEN 'Arrived'
                            WHEN final_values.status = 'En Route'
                                 AND final_values.derived_status = 'Scheduled'
                                THEN 'En Route'
                            ELSE final_values.derived_status
                        END AS next_status
                    FROM final_values
                ),
                updated AS (
                    UPDATE appointments AS appointment
                    SET
                        status = reconciled.next_status,
                        actual_arrival_time =
                            COALESCE(
                                appointment.actual_arrival_time,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.arrival_candidate
                                    THEN reconciled.arrival_candidate
                                END
                            ),
                        actual_arrival_delay_minutes =
                            COALESCE(
                                appointment.actual_arrival_delay_minutes,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.arrival_candidate
                                    THEN ROUND(
                                        EXTRACT(
                                            EPOCH FROM (
                                                reconciled.arrival_candidate
                                                - appointment.scheduled_time
                                            )
                                        ) / 60.0
                                    )::INTEGER
                                END
                            ),
                        actual_loading_start_time =
                            COALESCE(
                                appointment.actual_loading_start_time,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.start_candidate
                                    THEN reconciled.start_candidate
                                END
                            ),
                        actual_start_time =
                            COALESCE(
                                appointment.actual_start_time,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.start_candidate
                                    THEN reconciled.start_candidate
                                END
                            ),
                        actual_loading_end_time =
                            COALESCE(
                                appointment.actual_loading_end_time,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.end_candidate
                                    THEN reconciled.end_candidate
                                END
                            ),
                        actual_end_time =
                            COALESCE(
                                appointment.actual_end_time,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.end_candidate
                                    THEN reconciled.end_candidate
                                END
                            ),
                        actual_departure_time =
                            COALESCE(
                                appointment.actual_departure_time,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.dispatch_candidate
                                    THEN reconciled.dispatch_candidate
                                END
                            ),
                        actual_loading_duration_minutes =
                            COALESCE(
                                appointment.actual_loading_duration_minutes,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.end_candidate
                                    THEN reconciled.duration_minutes
                                END
                            ),
                        actual_turn_time_minutes =
                            COALESCE(
                                appointment.actual_turn_time_minutes,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.end_candidate
                                    THEN ROUND(
                                        ABS(
                                            EXTRACT(
                                                EPOCH FROM (
                                                    reconciled.end_candidate
                                                    - appointment.scheduled_time
                                                )
                                            )
                                        ) / 60.0
                                    )::INTEGER
                                END
                            ),
                        actual_sla_missed =
                            COALESCE(
                                appointment.actual_sla_missed,
                                CASE
                                    WHEN reconciled.local_now
                                         >= reconciled.end_candidate
                                    THEN (
                                        ROUND(
                                            ABS(
                                                EXTRACT(
                                                    EPOCH FROM (
                                                        reconciled.end_candidate
                                                        - appointment.scheduled_time
                                                    )
                                                )
                                            ) / 60.0
                                        )::INTEGER
                                        > appointment.sla_minutes
                                    )
                                END
                            ),
                        updated_at = reconciled.local_now
                    FROM reconciled
                    WHERE appointment.appt_id = reconciled.appt_id
                      AND (
                          appointment.status
                              IS DISTINCT FROM reconciled.next_status
                          OR (
                              appointment.actual_arrival_time IS NULL
                              AND reconciled.local_now
                                  >= reconciled.arrival_candidate
                          )
                          OR (
                              appointment.actual_loading_start_time IS NULL
                              AND reconciled.local_now
                                  >= reconciled.start_candidate
                          )
                          OR (
                              appointment.actual_loading_end_time IS NULL
                              AND reconciled.local_now
                                  >= reconciled.end_candidate
                          )
                          OR (
                              appointment.actual_departure_time IS NULL
                              AND reconciled.local_now
                                  >= reconciled.dispatch_candidate
                          )
                          OR (
                              appointment.actual_turn_time_minutes IS NULL
                              AND reconciled.local_now
                                  >= reconciled.end_candidate
                          )
                          OR (
                              appointment.actual_sla_missed IS NULL
                              AND reconciled.local_now
                                  >= reconciled.end_candidate
                          )
                      )
                    RETURNING appointment.appt_id
                )
                SELECT COUNT(*) AS updated_appointments
                FROM updated;
                """
            )
        ).mappings().one()

        self.db.commit()

        return DemoLifecycleResult(
            updated_appointments=int(
                result["updated_appointments"] or 0
            )
        )
