from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class DashboardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_summary(
        self,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        result = self.db.execute(
            text(
                """
                WITH filtered_appointments AS (
                    SELECT *
                    FROM appointments
                    WHERE appt_id LIKE 'DEMO%'
                      AND (
                          CAST(:facility_id AS VARCHAR) IS NULL
                          OR facility_id = :facility_id
                      )
                ),
                recommendation_usage AS (
    SELECT DISTINCT recommendation.appt_id

    FROM appointment_recommendations recommendation

    WHERE recommendation.status = 'Completed'

       OR EXISTS (
            SELECT 1
            FROM recommendation_actions action
            WHERE
                action.recommendation_id =
                    recommendation.recommendation_id
                AND action.decision_status =
                    'Accepted'
        )
)
                SELECT
                    COUNT(*) AS total_appointments,

                    COUNT(*) FILTER (
                        WHERE status = 'In Progress'
                    ) AS in_progress,

                    COUNT(*) FILTER (
                        WHERE status = 'Completed'
                    ) AS completed,

                    COUNT(*) FILTER (
                        WHERE actual_arrival_delay_minutes > 0
                    ) AS late_arrivals,

                    COUNT(*) FILTER (
                        WHERE actual_sla_missed = TRUE
                    ) AS sla_misses,

                    COUNT(*) FILTER (
                        WHERE actual_arrival_delay_minutes > 0
                          AND actual_sla_missed = FALSE
                    ) AS late_turned_on_time,

                    COUNT(*) FILTER (
                        WHERE actual_arrival_delay_minutes > 0
                          AND actual_sla_missed = FALSE
                          AND appt_id IN (
                              SELECT appt_id
                              FROM recommendation_usage
                          )
                    ) AS late_recovered_with_recommendations,

                    COUNT(*) FILTER (
                        WHERE actual_arrival_delay_minutes > 0
                          AND actual_sla_missed = FALSE
                          AND appt_id NOT IN (
                              SELECT appt_id
                              FROM recommendation_usage
                          )
                    ) AS late_recovered_without_recommendations,

                    ROUND(
                        AVG(actual_turn_time_minutes)
                        FILTER (
                            WHERE actual_turn_time_minutes
                                IS NOT NULL
                        ),
                        1
                    ) AS average_turn_time_minutes,

                    COALESCE(
                        ROUND(
                            SUM(
                                GREATEST(
                                    actual_turn_time_minutes
                                    - sla_minutes,
                                    0
                                )
                                / 60.0
                                * detention_cost_per_hour
                            )
                            FILTER (
                                WHERE actual_turn_time_minutes
                                    IS NOT NULL
                            ),
                            2
                        ),
                        0
                    ) AS detention_exposure

                FROM filtered_appointments;
                """
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
                      OR facility_id = :facility_id
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
        row = self.db.execute(
            text(
                """
                WITH filtered_appointments AS (
                    SELECT *
                    FROM appointments
                    WHERE appt_id LIKE 'DEMO%'
                      AND actual_arrival_delay_minutes > 0
                      AND status = 'Completed'
                      AND (
                          CAST(:facility_id AS VARCHAR)
                              IS NULL
                          OR facility_id = :facility_id
                      )
                ),
                recommendation_usage AS (
    SELECT DISTINCT recommendation.appt_id

    FROM appointment_recommendations recommendation

    WHERE recommendation.status = 'Completed'

       OR EXISTS (
            SELECT 1
            FROM recommendation_actions action
            WHERE
                action.recommendation_id =
                    recommendation.recommendation_id
                AND action.decision_status =
                    'Accepted'
        )
)
                SELECT
                    COUNT(*) FILTER (
                        WHERE actual_sla_missed = FALSE
                          AND appt_id IN (
                              SELECT appt_id
                              FROM recommendation_usage
                          )
                    ) AS recovered_with_recommendations,

                    COUNT(*) FILTER (
                        WHERE actual_sla_missed = FALSE
                          AND appt_id NOT IN (
                              SELECT appt_id
                              FROM recommendation_usage
                          )
                    ) AS recovered_without_recommendations,

                    COUNT(*) FILTER (
                        WHERE actual_sla_missed = TRUE
                    ) AS missed_sla

                FROM filtered_appointments;
                """
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
                    row["missed_sla"] or 0
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
                          AND a.actual_sla_missed = FALSE
                    ) AS on_time_turns,

                    COUNT(a.appt_id) FILTER (
                        WHERE a.status = 'Completed'
                          AND a.actual_sla_missed = TRUE
                    ) AS missed_turns,

                    ROUND(
                        100.0
                        * COUNT(a.appt_id) FILTER (
                            WHERE a.status = 'Completed'
                              AND a.actual_sla_missed
                                  = FALSE
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
                WITH risk_groups AS (
                    SELECT
                        CASE
                            WHEN p.turn_risk_score < 30
                                THEN 'Low'
                            WHEN p.turn_risk_score < 60
                                THEN 'Medium'
                            WHEN p.turn_risk_score < 80
                                THEN 'High'
                            ELSE 'Critical'
                        END AS risk_level,

                        CASE
                            WHEN p.turn_risk_score < 30 THEN 1
                            WHEN p.turn_risk_score < 60 THEN 2
                            WHEN p.turn_risk_score < 80 THEN 3
                            ELSE 4
                        END AS sort_order

                    FROM appointment_predictions p

                    JOIN appointments a
                        ON a.appt_id = p.appt_id

                    WHERE a.appt_id LIKE 'DEMO%'
                    AND (
                        CAST(:facility_id AS VARCHAR) IS NULL
                        OR a.facility_id = :facility_id
                    )
                )

                SELECT
                    risk_level,
                    COUNT(*) AS appointment_count
                FROM risk_groups
                GROUP BY risk_level, sort_order
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
            WHERE actual_sla_missed = FALSE
        )
        / NULLIF(COUNT(*), 0),
        1
    ) AS turn_compliance_percent

                FROM appointments

               WHERE appt_id LIKE 'DEMO%'
  AND status = 'Completed'
  AND (
      CAST(:facility_id AS VARCHAR) IS NULL
      OR facility_id = :facility_id
  )

                GROUP BY DATE(scheduled_time)
                ORDER BY operation_date;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        return [dict(row) for row in rows]

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
                      OR a.facility_id = :facility_id
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