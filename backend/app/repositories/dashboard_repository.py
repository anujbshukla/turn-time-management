from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories.outcome_rules import (
    completed_sla_met_sql,
    completed_sla_missed_sql,
    recommendation_used_exists_sql,
)


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_summary(
        self,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        sla_met = completed_sla_met_sql("appointment")
        sla_missed = completed_sla_missed_sql("appointment")
        recommendation_used = recommendation_used_exists_sql(
            "appointment"
        )

        result = self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_appointments,

                    COUNT(*) FILTER (
                        WHERE appointment.status = 'In Progress'
                    ) AS in_progress,

                    COUNT(*) FILTER (
                        WHERE appointment.status = 'Completed'
                    ) AS completed,

                    COUNT(*) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                    ) AS late_arrivals,

                    COUNT(*) FILTER (
                        WHERE ({sla_missed})
                    ) AS sla_misses,

                    COUNT(*) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                          AND ({sla_met})
                    ) AS late_turned_on_time,

                    COUNT(*) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                          AND ({sla_met})
                          AND ({recommendation_used})
                    ) AS late_recovered_with_recommendations,

                    COUNT(*) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                          AND ({sla_met})
                          AND NOT ({recommendation_used})
                    ) AS late_recovered_without_recommendations,

                    ROUND(
                        AVG(appointment.actual_turn_time_minutes)
                        FILTER (
                            WHERE appointment.actual_turn_time_minutes
                                IS NOT NULL
                        ),
                        1
                    ) AS average_turn_time_minutes,

                    COALESCE(
                        ROUND(
                            SUM(
                                GREATEST(
                                    appointment.actual_turn_time_minutes
                                    - appointment.sla_minutes,
                                    0
                                )
                                / 60.0
                                * appointment.detention_cost_per_hour
                            )
                            FILTER (
                                WHERE appointment.actual_turn_time_minutes
                                    IS NOT NULL
                            ),
                            2
                        ),
                        0
                    ) AS detention_exposure

                FROM appointments AS appointment

                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  );
                """.format(
                    sla_met=sla_met,
                    sla_missed=sla_missed,
                    recommendation_used=recommendation_used,
                )
            ),
            {"facility_id": facility_id},
        ).mappings().one()

        summary = dict(result)

        recovered = (
            summary["late_turned_on_time"] or 0
        )

        recommendation_recovered = (
            summary[
                "late_recovered_with_recommendations"
            ]
            or 0
        )

        summary["recovery_contribution_percent"] = (
            round(
                recommendation_recovered
                / recovered
                * 100,
                1,
            )
            if recovered > 0
            else 0.0
        )

        return summary

    def get_status_distribution(
        self,
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    status,
                    COUNT(*) AS appointment_count
                FROM appointments
                WHERE appt_id LIKE 'DEMO%'
                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR facility_id = CAST(:facility_id AS VARCHAR)
                  )
                GROUP BY status
                ORDER BY appointment_count DESC;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        return [dict(row) for row in rows]

    def get_late_outcomes(
        self,
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        sla_met = completed_sla_met_sql("appointment")
        sla_missed = completed_sla_missed_sql("appointment")
        recommendation_used = recommendation_used_exists_sql(
            "appointment"
        )

        row = self.db.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE ({sla_met})
                          AND ({recommendation_used})
                    ) AS recovered_with_recommendations,

                    COUNT(*) FILTER (
                        WHERE ({sla_met})
                          AND NOT ({recommendation_used})
                    ) AS recovered_without_recommendations,

                    COUNT(*) FILTER (
                        WHERE ({sla_missed})
                    ) AS missed_sla

                FROM appointments AS appointment

                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND appointment.actual_arrival_delay_minutes > 0
                  AND appointment.status = 'Completed'
                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  );
                """.format(
                    sla_met=sla_met,
                    sla_missed=sla_missed,
                    recommendation_used=recommendation_used,
                )
            ),
            {"facility_id": facility_id},
        ).mappings().one()

        return [
            {
                "outcome": "Recovered with recommendations",
                "appointment_count": (
                    row[
                        "recovered_with_recommendations"
                    ]
                    or 0
                ),
            },
            {
                "outcome": "Recovered without recommendations",
                "appointment_count": (
                    row[
                        "recovered_without_recommendations"
                    ]
                    or 0
                ),
            },
            {
                "outcome": "Missed SLA",
                "appointment_count": (
                    row["missed_sla"]
                    or 0
                ),
            },
        ]

    def get_facility_performance(
        self,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    f.facility_id,
                    f.facility_name,

                    COUNT(a.appt_id) FILTER (
                        WHERE a.status = 'Completed'
                    ) AS completed_appointments,

                    COUNT(a.appt_id) FILTER (
                        WHERE a.status = 'Completed'
                          AND a.actual_turn_time_minutes IS NOT NULL
                          AND a.actual_turn_time_minutes <= a.sla_minutes
                    ) AS on_time_turns,

                    COUNT(a.appt_id) FILTER (
                        WHERE a.status = 'Completed'
                          AND (
                              a.actual_turn_time_minutes > a.sla_minutes
                              OR (
                                  a.actual_turn_time_minutes IS NULL
                                  AND a.actual_sla_missed = TRUE
                              )
                          )
                    ) AS missed_turns,

                    ROUND(
                        100.0
                        * COUNT(a.appt_id) FILTER (
                            WHERE a.status = 'Completed'
                              AND a.actual_turn_time_minutes IS NOT NULL
                              AND a.actual_turn_time_minutes <= a.sla_minutes
                        )
                        / NULLIF(
                            COUNT(a.appt_id) FILTER (
                                WHERE a.status = 'Completed'
                            ),
                            0
                        ),
                        1
                    ) AS turn_compliance_percent

                FROM facilities f

                LEFT JOIN appointments a
                    ON a.facility_id = f.facility_id
                   AND a.appt_id LIKE 'DEMO%'

                GROUP BY
                    f.facility_id,
                    f.facility_name

                ORDER BY f.facility_name;
                """
            )
        ).mappings().all()

        return [dict(row) for row in rows]

    def get_risk_distribution(
        self,
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                WITH latest_predictions AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.turn_risk_score

                    FROM appointment_predictions AS prediction

                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                ),
                risk_groups AS (
                    SELECT
                        CASE
                            WHEN prediction.turn_risk_score < 30
                                THEN 'Low'
                            WHEN prediction.turn_risk_score < 60
                                THEN 'Medium'
                            WHEN prediction.turn_risk_score < 80
                                THEN 'High'
                            ELSE 'Critical'
                        END AS risk_level,

                        CASE
                            WHEN prediction.turn_risk_score < 30 THEN 1
                            WHEN prediction.turn_risk_score < 60 THEN 2
                            WHEN prediction.turn_risk_score < 80 THEN 3
                            ELSE 4
                        END AS sort_order

                    FROM appointments AS appointment

                    JOIN latest_predictions AS prediction
                        ON prediction.appt_id =
                           appointment.appt_id

                    WHERE appointment.appt_id LIKE 'DEMO%'

                      AND (
                          CAST(:facility_id AS VARCHAR) IS NULL
                          OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                      )
                )

                SELECT
                    risk_level,
                    COUNT(*) AS appointment_count

                FROM risk_groups

                GROUP BY
                    risk_level,
                    sort_order

                ORDER BY sort_order;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        return [dict(row) for row in rows]

    def get_daily_compliance_trend(
        self,
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
    DATE(scheduled_time) AS operation_date,

    COUNT(*) AS completed_appointments,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE actual_turn_time_minutes IS NOT NULL
                              AND actual_turn_time_minutes <= sla_minutes
        )
        / NULLIF(COUNT(*), 0),
        1
    ) AS turn_compliance_percent

                FROM appointments

               WHERE appt_id LIKE 'DEMO%'
  AND status = 'Completed'
  AND (
      CAST(:facility_id AS VARCHAR) IS NULL
      OR facility_id = CAST(:facility_id AS VARCHAR)
  )

                GROUP BY DATE(scheduled_time)
                ORDER BY operation_date;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        return [dict(row) for row in rows]


    def get_delay_sla_reasons(
        self,
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                WITH classified AS (
                    SELECT
                        a.*,
                        d.dock_name,
                        CASE
                            WHEN a.weather_severity >= 2 THEN 'Weather disruption'
                            WHEN a.traffic_severity >= 2 THEN 'Traffic disruption'
                            WHEN a.actual_arrival_delay_minutes >= 30 THEN 'Carrier delay'
                            WHEN a.actual_arrival_time IS NOT NULL
                              AND a.actual_start_time IS NOT NULL
                              AND EXTRACT(EPOCH FROM (a.actual_start_time - a.actual_arrival_time)) / 60 >= 20
                                THEN 'Dock congestion'
                            WHEN a.actual_loading_duration_minutes IS NOT NULL
                              AND p.predicted_duration_minutes IS NOT NULL
                              AND a.actual_loading_duration_minutes > p.predicted_duration_minutes * 1.20
                                THEN 'Loading overrun'
                            ELSE 'Operational variance'
                        END AS reason
                    FROM appointments a
                    LEFT JOIN appointment_predictions p ON p.appt_id = a.appt_id
                    LEFT JOIN docks d ON d.dock_id = a.assigned_dock_id
                    WHERE a.appt_id LIKE 'DEMO%'
                      AND (
                          a.actual_arrival_delay_minutes > 0
                          OR a.actual_turn_time_minutes > a.sla_minutes
                          OR (
                              a.actual_turn_time_minutes IS NULL
                              AND a.actual_sla_missed = TRUE
                          )
                      )
                      AND (CAST(:facility_id AS VARCHAR) IS NULL OR a.facility_id = CAST(:facility_id AS VARCHAR))
                ), totals AS (
                    SELECT COUNT(*) FILTER (WHERE actual_arrival_delay_minutes > 0) AS total_late
                    FROM classified
                )
                SELECT
                    reason,
                    COUNT(*) FILTER (WHERE actual_arrival_delay_minutes > 0) AS late_appointments,
                    COUNT(*) FILTER (WHERE (
                            actual_turn_time_minutes > sla_minutes
                            OR (
                                actual_turn_time_minutes IS NULL
                                AND actual_sla_missed = TRUE
                            )
                        )) AS sla_misses,
                    ROUND(100.0 * COUNT(*) FILTER (WHERE actual_arrival_delay_minutes > 0) / NULLIF((SELECT total_late FROM totals), 0), 1) AS late_share_percent,
                    ROUND(AVG(actual_arrival_delay_minutes) FILTER (WHERE actual_arrival_delay_minutes > 0), 1) AS average_delay_minutes,
                    MODE() WITHIN GROUP (ORDER BY dock_name) AS most_affected_dock
                FROM classified
                GROUP BY reason
                ORDER BY sla_misses DESC, late_appointments DESC;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_recovery_plan_performance(
        self,
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    ra.action_code,
                    ra.action_title AS recovery_plan,
                    COUNT(*) FILTER (WHERE ra.status IN ('Accepted', 'Completed')) AS times_used,
                    ROUND(100.0 * COUNT(*) FILTER (WHERE ra.status IN ('Accepted', 'Completed')) / NULLIF(COUNT(*), 0), 1) AS acceptance_rate,
                    COUNT(*) FILTER (
                        WHERE ra.status IN ('Accepted', 'Completed')
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_turn_time_minutes IS NOT NULL
                          AND a.actual_turn_time_minutes <= a.sla_minutes
                    ) AS sla_recoveries,
                    ROUND(100.0 * COUNT(*) FILTER (
                        WHERE ra.status IN ('Accepted', 'Completed')
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_turn_time_minutes IS NOT NULL
                          AND a.actual_turn_time_minutes <= a.sla_minutes
                    ) / NULLIF(COUNT(*) FILTER (WHERE ra.status IN ('Accepted', 'Completed')), 0), 1) AS success_rate,
                    ROUND(AVG(ra.estimated_minutes_saved) FILTER (WHERE ra.status IN ('Accepted', 'Completed')), 1) AS average_minutes_saved,
                    ROUND(COALESCE(SUM(
                        CASE WHEN ra.status IN ('Accepted', 'Completed')
                        THEN GREATEST(COALESCE(ar.estimated_savings, 0) - COALESCE(ra.estimated_action_cost, 0), 0)
                        ELSE 0 END
                    ), 0), 2) AS net_savings
                FROM recommendation_actions ra
                JOIN appointment_recommendations ar ON ar.recommendation_id = ra.recommendation_id
                JOIN appointments a ON a.appt_id = ar.appt_id
                WHERE a.appt_id LIKE 'DEMO%'
                  AND (CAST(:facility_id AS VARCHAR) IS NULL OR a.facility_id = CAST(:facility_id AS VARCHAR))
                GROUP BY ra.action_code, ra.action_title
                ORDER BY times_used DESC, success_rate DESC;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_intelligence_filter_reference_data(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, list[dict[str, str | None]]]:
        """Return cascading options for Root Cause Intelligence.

        Options are sourced only from appointments that can contribute to the
        Delay & SLA Reasons or Recovery Plans views. Each option list applies
        every active analysis filter except its own dimension.
        """

        intelligence_population = """
            (
                a.actual_arrival_delay_minutes > 0
                OR a.actual_turn_time_minutes > a.sla_minutes
                OR (
                    a.actual_turn_time_minutes IS NULL
                    AND a.actual_sla_missed = TRUE
                )
                OR EXISTS (
                    SELECT 1
                    FROM appointment_recommendations ar
                    JOIN recommendation_actions ra
                      ON ra.recommendation_id = ar.recommendation_id
                    WHERE ar.appt_id = a.appt_id
                )
            )
        """

        def build_conditions(exclude: str) -> tuple[str, dict[str, object]]:
            conditions = [
                "a.appt_id LIKE 'DEMO%'",
                intelligence_population,
            ]
            params: dict[str, object] = {}

            if facility_id:
                conditions.append("a.facility_id = :facility_id")
                params["facility_id"] = facility_id
            if exclude != "customer" and customer_id:
                conditions.append("a.customer_id = :customer_id")
                params["customer_id"] = customer_id
            if exclude != "carrier" and carrier_id:
                conditions.append("a.carrier_id = :carrier_id")
                params["carrier_id"] = carrier_id
            if exclude != "appointment_type" and appointment_type:
                conditions.append(
                    "LOWER(a.appointment_type) = LOWER(:appointment_type)"
                )
                params["appointment_type"] = appointment_type
            if date_from:
                conditions.append("a.scheduled_time >= :date_from")
                params["date_from"] = date_from
            if date_to:
                conditions.append("a.scheduled_time < :date_to")
                params["date_to"] = date_to

            return " AND ".join(conditions), params

        customer_where, customer_params = build_conditions("customer")
        carrier_where, carrier_params = build_conditions("carrier")
        type_where, type_params = build_conditions("appointment_type")

        customers = self.db.execute(
            text(
                f"""
                SELECT DISTINCT
                    a.customer_id AS id,
                    COALESCE(c.customer_name, a.customer_name, a.customer_id) AS label,
                    NULL::VARCHAR AS facility_id
                FROM public.appointments a
                LEFT JOIN customers c ON c.customer_id = a.customer_id
                WHERE {customer_where}
                  AND a.customer_id IS NOT NULL
                ORDER BY label;
                """
            ),
            customer_params,
        ).mappings().all()

        carriers = self.db.execute(
            text(
                f"""
                SELECT DISTINCT
                    a.carrier_id AS id,
                    COALESCE(c.carrier_name, a.carrier_id) AS label,
                    NULL::VARCHAR AS facility_id
                FROM public.appointments a
                LEFT JOIN carriers c ON c.carrier_id = a.carrier_id
                WHERE {carrier_where}
                  AND a.carrier_id IS NOT NULL
                ORDER BY label;
                """
            ),
            carrier_params,
        ).mappings().all()

        appointment_types = self.db.execute(
            text(
                f"""
                SELECT DISTINCT
                    a.appointment_type AS id,
                    a.appointment_type AS label,
                    NULL::VARCHAR AS facility_id
                FROM public.appointments a
                WHERE {type_where}
                  AND a.appointment_type IS NOT NULL
                ORDER BY label;
                """
            ),
            type_params,
        ).mappings().all()

        return {
            "facilities": [],
            "customers": [dict(row) for row in customers],
            "carriers": [dict(row) for row in carriers],
            "appointment_types": [dict(row) for row in appointment_types],
        }

    def get_recommendation_savings(
        self,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                SELECT
                    ROUND(COALESCE(SUM(ar.estimated_loss_without_action), 0), 2) AS without_recommendations,
                    ROUND(COALESCE(SUM(
                        CASE WHEN ar.status IN ('Accepted', 'Completed')
                        THEN GREATEST(ar.estimated_loss_without_action - ar.estimated_savings, 0)
                        ELSE ar.estimated_loss_without_action END
                    ), 0), 2) AS detention_with_recommendations,
                    ROUND(COALESCE(SUM(
                        CASE WHEN ar.status IN ('Accepted', 'Completed')
                        THEN ar.estimated_cost_of_action ELSE 0 END
                    ), 0), 2) AS action_cost,
                    ROUND(COALESCE(SUM(
                        CASE WHEN ar.status IN ('Accepted', 'Completed')
                        THEN ar.estimated_savings ELSE 0 END
                    ), 0), 2) AS gross_savings
                FROM appointment_recommendations ar
                JOIN appointments a ON a.appt_id = ar.appt_id
                WHERE a.appt_id LIKE 'DEMO%'
                  AND (CAST(:facility_id AS VARCHAR) IS NULL OR a.facility_id = CAST(:facility_id AS VARCHAR));
                """
            ),
            {"facility_id": facility_id},
        ).mappings().one()
        result = dict(row)
        net = float(result.get("gross_savings") or 0) - float(result.get("action_cost") or 0)
        result["net_savings"] = round(net, 2)
        result["with_recommendations"] = round(float(result.get("detention_with_recommendations") or 0) + float(result.get("action_cost") or 0), 2)
        result["roi"] = round(net / float(result.get("action_cost") or 0), 2) if float(result.get("action_cost") or 0) > 0 else 0.0
        without = float(result.get("without_recommendations") or 0)
        result["cost_reduction_percent"] = round(net / without * 100, 1) if without > 0 else 0.0
        return result

    def get_high_risk_appointments(
        self,
        facility_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    a.appt_id,
                    a.customer_name,
                    f.facility_name,
                    c.carrier_name,
                    d.dock_name,
                    a.status,
                    a.scheduled_time,
                    a.estimated_arrival_time,
                    a.actual_arrival_delay_minutes,
                    a.pallet_count,
                    a.sku_count,
                    p.predicted_duration_minutes,
                    p.turn_risk_score,
                    p.sla_recovery_probability,
                    p.predicted_missed,

                    r.recommended_action,
                    r.estimated_savings

                FROM appointments a

                JOIN facilities f
                    ON f.facility_id = a.facility_id

                LEFT JOIN carriers c
                    ON c.carrier_id = a.carrier_id

                LEFT JOIN docks d
                    ON d.dock_id = a.assigned_dock_id

                JOIN appointment_predictions p
                    ON p.appt_id = a.appt_id

                LEFT JOIN LATERAL (
                    SELECT
                        recommended_action,
                        estimated_savings
                    FROM appointment_recommendations
                    WHERE appt_id = a.appt_id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) r ON TRUE

                WHERE a.appt_id LIKE 'DEMO%'
                  AND p.turn_risk_score >= 65
                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR a.facility_id = CAST(:facility_id AS VARCHAR)
                  )

                ORDER BY p.turn_risk_score DESC
                LIMIT :limit;
                """
            ),
            {
                "facility_id": facility_id,
                "limit": limit,
            },
        ).mappings().all()

        return [dict(row) for row in rows]
    def get_what_if_candidates(
        self,
        facility_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return prediction-level data used by the dashboard simulation.

        The query is read-only and deliberately returns one latest prediction
        per demo appointment. The simulation service owns all scenario math.
        """
        rows = self.db.execute(
            text(
                """
                WITH latest_predictions AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.predicted_delay_minutes,
                        prediction.predicted_duration_minutes,
                        prediction.sla_miss_probability,
                        prediction.turn_risk_score
                    FROM appointment_predictions prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.prediction_id DESC
                )
                SELECT
                    appointment.appt_id,
                    appointment.status,
                    appointment.actual_arrival_delay_minutes,
                    appointment.actual_sla_missed,
                    appointment.sla_minutes,
                    appointment.detention_cost_per_hour,
                    appointment.pallet_count,
                    appointment.sku_count,
                    appointment.assigned_dock_id,
                    prediction.predicted_delay_minutes,
                    prediction.predicted_duration_minutes,
                    prediction.sla_miss_probability,
                    prediction.turn_risk_score
                FROM appointments appointment
                JOIN latest_predictions prediction
                    ON prediction.appt_id = appointment.appt_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR appointment.facility_id = CAST(:facility_id AS VARCHAR)
                  )
                ORDER BY
                    prediction.turn_risk_score DESC,
                    appointment.scheduled_time;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        return [dict(row) for row in rows]
