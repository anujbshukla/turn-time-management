from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class CopilotAnalyticsRepository:
    """Read-only analytical access for the Global Warehouse Copilot."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def appointment_summary(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        product_id: str | None = None,
        appointment_type: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        return dict(
            self.db.execute(
                text(
                    """
                    WITH latest_prediction AS (
                        SELECT DISTINCT ON (prediction.appt_id)
                            prediction.appt_id,
                            prediction.predicted_duration_minutes,
                            prediction.predicted_delay_minutes,
                            prediction.sla_miss_probability,
                            prediction.turn_risk_score,
                            prediction.predicted_missed
                        FROM appointment_predictions AS prediction
                        ORDER BY
                            prediction.appt_id,
                            prediction.generated_at DESC,
                            prediction.prediction_id DESC
                    ),
                    filtered AS (
                        SELECT DISTINCT
                            appointment.appt_id,
                            appointment.status,
                            appointment.appointment_type,
                            appointment.actual_arrival_delay_minutes,
                            appointment.actual_turn_time_minutes,
                            appointment.sla_minutes,
                            appointment.detention_cost_per_hour,
                            prediction.predicted_duration_minutes,
                            prediction.predicted_delay_minutes,
                            prediction.sla_miss_probability,
                            prediction.turn_risk_score,
                            prediction.predicted_missed
                        FROM appointments AS appointment
                        LEFT JOIN latest_prediction AS prediction
                            ON prediction.appt_id = appointment.appt_id
                        LEFT JOIN appointment_products AS line
                            ON line.appt_id = appointment.appt_id
                        WHERE appointment.appt_id LIKE 'DEMO%'

                          AND (
                              CAST(:facility_id AS VARCHAR) IS NULL
                              OR appointment.facility_id = :facility_id
                          )

                          AND (
                              CAST(:customer_id AS VARCHAR) IS NULL
                              OR appointment.customer_id = :customer_id
                          )

                          AND (
                              CAST(:carrier_id AS VARCHAR) IS NULL
                              OR appointment.carrier_id = :carrier_id
                          )

                          AND (
                              CAST(:product_id AS VARCHAR) IS NULL
                              OR line.product_id = :product_id
                          )

                          AND (
                              CAST(:appointment_type AS VARCHAR) IS NULL
                              OR appointment.appointment_type =
                                 :appointment_type
                          )

                          AND (
                              CAST(:status AS VARCHAR) IS NULL
                              OR appointment.status = :status
                          )

                          AND (
                              CAST(:date_from AS TIMESTAMP) IS NULL
                              OR appointment.scheduled_time >= :date_from
                          )

                          AND (
                              CAST(:date_to AS TIMESTAMP) IS NULL
                              OR appointment.scheduled_time < :date_to
                          )

                          AND (
                              CAST(:risk_level AS VARCHAR) IS NULL

                              OR (
                                  :risk_level = 'Low'
                                  AND prediction.turn_risk_score < 30
                              )

                              OR (
                                  :risk_level = 'Medium'
                                  AND prediction.turn_risk_score >= 30
                                  AND prediction.turn_risk_score < 60
                              )

                              OR (
                                  :risk_level = 'High'
                                  AND prediction.turn_risk_score >= 60
                                  AND prediction.turn_risk_score < 80
                              )

                              OR (
                                  :risk_level = 'Critical'
                                  AND prediction.turn_risk_score >= 80
                              )
                          )
                    )

                    SELECT
                        COUNT(*) AS appointment_count,

                        COUNT(*) FILTER (
                            WHERE actual_arrival_delay_minutes > 0
                        ) AS late_appointments,

                        COUNT(*) FILTER (
                            WHERE actual_turn_time_minutes > sla_minutes
                               OR (
                                    actual_turn_time_minutes IS NULL
                                    AND predicted_missed = TRUE
                               )
                        ) AS sla_risk_or_misses,

                        COUNT(*) FILTER (
                            WHERE predicted_missed = TRUE
                        ) AS predicted_sla_misses,

                        COUNT(*) FILTER (
                            WHERE turn_risk_score >= 80
                        ) AS critical_appointments,

                        ROUND(
                            AVG(actual_arrival_delay_minutes)
                            FILTER (
                                WHERE actual_arrival_delay_minutes
                                      IS NOT NULL
                            ),
                            1
                        ) AS average_delay_minutes,

                        ROUND(
                            AVG(actual_turn_time_minutes)
                            FILTER (
                                WHERE actual_turn_time_minutes
                                      IS NOT NULL
                            ),
                            1
                        ) AS average_actual_turn_time_minutes,

                        ROUND(
                            AVG(predicted_duration_minutes)
                            FILTER (
                                WHERE predicted_duration_minutes
                                      IS NOT NULL
                            ),
                            1
                        ) AS average_predicted_duration_minutes,

                        ROUND(
                            AVG(turn_risk_score)
                            FILTER (
                                WHERE turn_risk_score IS NOT NULL
                            ),
                            1
                        ) AS average_risk_score,

                        ROUND(
                            COALESCE(
                                SUM(
                                    GREATEST(
                                        COALESCE(
                                            actual_turn_time_minutes,
                                            0
                                        ) - sla_minutes,
                                        0
                                    )
                                    / 60.0
                                    * detention_cost_per_hour
                                ),
                                0
                            ),
                            2
                        ) AS detention_exposure

                    FROM filtered;
                    """
                ),
                {
                    "facility_id": facility_id,
                    "customer_id": customer_id,
                    "carrier_id": carrier_id,
                    "product_id": product_id,
                    "appointment_type": appointment_type,
                    "status": status,
                    "risk_level": risk_level,
                    "date_from": date_from,
                    "date_to": date_to,
                },
            ).mappings().one()
        )

    def grouped_appointment_metrics(
        self,
        *,
        group_by: str,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        product_id: str | None = None,
        appointment_type: str | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        group_expressions = {
            "facility": (
                "appointment.facility_id",
                "facility.facility_name",
            ),
            "customer": (
                "appointment.customer_id",
                "COALESCE(customer.customer_name, "
                "appointment.customer_name)",
            ),
            "carrier": (
                "appointment.carrier_id",
                "carrier.carrier_name",
            ),
            "dock": (
                "appointment.assigned_dock_id",
                "dock.dock_name",
            ),
            "appointment_type": (
                "appointment.appointment_type",
                "appointment.appointment_type",
            ),
            "status": (
                "appointment.status",
                "appointment.status",
            ),
            "product": (
                "product.product_id",
                "product.product_name",
            ),
        }

        if group_by not in group_expressions:
            raise ValueError(
                f"Unsupported analytics grouping: {group_by}"
            )

        group_id, group_label = group_expressions[group_by]

        query = """
            WITH latest_prediction AS (
                SELECT DISTINCT ON (prediction.appt_id)
                    prediction.appt_id,
                    prediction.turn_risk_score,
                    prediction.predicted_missed
                FROM appointment_predictions AS prediction
                ORDER BY
                    prediction.appt_id,
                    prediction.generated_at DESC,
                    prediction.prediction_id DESC
            )

            SELECT
                {group_id} AS group_id,
                {group_label} AS group_label,

                COUNT(DISTINCT appointment.appt_id)
                    AS appointment_count,

                COUNT(DISTINCT appointment.appt_id) FILTER (
                    WHERE appointment.actual_arrival_delay_minutes > 0
                ) AS late_appointments,

                COUNT(DISTINCT appointment.appt_id) FILTER (
                    WHERE appointment.actual_turn_time_minutes >
                          appointment.sla_minutes
                       OR prediction.predicted_missed = TRUE
                ) AS sla_risk_or_misses,

                COUNT(DISTINCT appointment.appt_id) FILTER (
                    WHERE prediction.turn_risk_score >= 80
                ) AS critical_appointments,

                ROUND(
                    AVG(
                        appointment.actual_arrival_delay_minutes
                    )
                    FILTER (
                        WHERE
                            appointment.actual_arrival_delay_minutes
                            IS NOT NULL
                    ),
                    1
                ) AS average_delay_minutes,

                ROUND(
                    AVG(appointment.actual_turn_time_minutes)
                    FILTER (
                        WHERE appointment.actual_turn_time_minutes
                              IS NOT NULL
                    ),
                    1
                ) AS average_turn_time_minutes,

                ROUND(
                    AVG(prediction.turn_risk_score)
                    FILTER (
                        WHERE prediction.turn_risk_score
                              IS NOT NULL
                    ),
                    1
                ) AS average_risk_score,

                ROUND(
                    COALESCE(
                        SUM(
                            GREATEST(
                                COALESCE(
                                    appointment.actual_turn_time_minutes,
                                    0
                                ) - appointment.sla_minutes,
                                0
                            )
                            / 60.0
                            * appointment.detention_cost_per_hour
                        ),
                        0
                    ),
                    2
                ) AS detention_exposure

            FROM appointments AS appointment

            LEFT JOIN facilities AS facility
                ON facility.facility_id =
                   appointment.facility_id

            LEFT JOIN customers AS customer
                ON customer.customer_id =
                   appointment.customer_id

            LEFT JOIN carriers AS carrier
                ON carrier.carrier_id =
                   appointment.carrier_id

            LEFT JOIN docks AS dock
                ON dock.dock_id =
                   appointment.assigned_dock_id

            LEFT JOIN appointment_products AS line
                ON line.appt_id =
                   appointment.appt_id

            LEFT JOIN products AS product
                ON product.product_id =
                   line.product_id

            LEFT JOIN latest_prediction AS prediction
                ON prediction.appt_id =
                   appointment.appt_id

            WHERE appointment.appt_id LIKE 'DEMO%'

              AND (
                  CAST(:facility_id AS VARCHAR) IS NULL
                  OR appointment.facility_id = :facility_id
              )

              AND (
                  CAST(:customer_id AS VARCHAR) IS NULL
                  OR appointment.customer_id = :customer_id
              )

              AND (
                  CAST(:carrier_id AS VARCHAR) IS NULL
                  OR appointment.carrier_id = :carrier_id
              )

              AND (
                  CAST(:product_id AS VARCHAR) IS NULL
                  OR line.product_id = :product_id
              )

              AND (
                  CAST(:appointment_type AS VARCHAR) IS NULL
                  OR appointment.appointment_type =
                     :appointment_type
              )

              AND (
                  CAST(:status AS VARCHAR) IS NULL
                  OR appointment.status = :status
              )

              AND (
                  CAST(:date_from AS TIMESTAMP) IS NULL
                  OR appointment.scheduled_time >= :date_from
              )

              AND (
                  CAST(:date_to AS TIMESTAMP) IS NULL
                  OR appointment.scheduled_time < :date_to
              )

              AND {group_id} IS NOT NULL

            GROUP BY
                {group_id},
                {group_label}

            ORDER BY appointment_count DESC

            LIMIT :limit;
        """.format(
            group_id=group_id,
            group_label=group_label,
        )

        rows = self.db.execute(
            text(query),
            {
                "facility_id": facility_id,
                "customer_id": customer_id,
                "carrier_id": carrier_id,
                "product_id": product_id,
                "appointment_type": appointment_type,
                "status": status,
                "date_from": date_from,
                "date_to": date_to,
                "limit": min(50, max(1, limit)),
            },
        ).mappings().all()

        return [dict(row) for row in rows]

    def top_risk_appointments(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                WITH latest_prediction AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.turn_risk_score,
                        prediction.sla_miss_probability,
                        prediction.predicted_duration_minutes,
                        prediction.predicted_missed
                    FROM appointment_predictions AS prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                )

                SELECT
                    appointment.appt_id,
                    appointment.customer_name,
                    facility.facility_name,
                    carrier.carrier_name,
                    appointment.appointment_type,
                    appointment.status,
                    appointment.scheduled_time,
                    prediction.turn_risk_score,
                    prediction.sla_miss_probability,
                    prediction.predicted_duration_minutes,
                    prediction.predicted_missed

                FROM appointments AS appointment

                JOIN latest_prediction AS prediction
                    ON prediction.appt_id =
                       appointment.appt_id

                LEFT JOIN facilities AS facility
                    ON facility.facility_id =
                       appointment.facility_id

                LEFT JOIN carriers AS carrier
                    ON carrier.carrier_id =
                       appointment.carrier_id

                WHERE appointment.appt_id LIKE 'DEMO%'

                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR appointment.facility_id = :facility_id
                  )

                  AND (
                      CAST(:customer_id AS VARCHAR) IS NULL
                      OR appointment.customer_id = :customer_id
                  )

                  AND (
                      CAST(:carrier_id AS VARCHAR) IS NULL
                      OR appointment.carrier_id = :carrier_id
                  )

                  AND (
                      CAST(:appointment_type AS VARCHAR) IS NULL
                      OR appointment.appointment_type =
                         :appointment_type
                  )

                  AND (
                      CAST(:date_from AS TIMESTAMP) IS NULL
                      OR appointment.scheduled_time >= :date_from
                  )

                  AND (
                      CAST(:date_to AS TIMESTAMP) IS NULL
                      OR appointment.scheduled_time < :date_to
                  )

                ORDER BY
                    prediction.turn_risk_score DESC,
                    appointment.scheduled_time

                LIMIT :limit;
                """
            ),
            {
                "facility_id": facility_id,
                "customer_id": customer_id,
                "carrier_id": carrier_id,
                "appointment_type": appointment_type,
                "date_from": date_from,
                "date_to": date_to,
                "limit": min(25, max(1, limit)),
            },
        ).mappings().all()

        return [dict(row) for row in rows]