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

    def advanced_appointment_summary(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        product_id: str | None = None,
        appointment_type: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        pallet_min: int | None = None,
        pallet_max: int | None = None,
        sku_min: int | None = None,
        sku_max: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        row = self.db.execute(
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
                    FROM appointment_predictions prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                ),
                filtered AS (
                    SELECT DISTINCT
                        appointment.appt_id,
                        appointment.actual_arrival_delay_minutes,
                        appointment.actual_turn_time_minutes,
                        appointment.sla_minutes,
                        appointment.detention_cost_per_hour,
                        appointment.pallet_count,
                        appointment.sku_count,
                        prediction.predicted_duration_minutes,
                        prediction.predicted_missed,
                        prediction.turn_risk_score,
                        allocation.dock_congestion_percent,
                        allocation.labor_utilization_percent,
                        allocation.forklift_utilization_percent
                    FROM appointments appointment
                    LEFT JOIN latest_prediction prediction
                      ON prediction.appt_id = appointment.appt_id
                    LEFT JOIN appointment_products line
                      ON line.appt_id = appointment.appt_id
                    LEFT JOIN appointment_resource_allocations allocation
                      ON allocation.appt_id = appointment.appt_id
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
                          OR appointment.appointment_type = :appointment_type
                      )
                      AND (
                          CAST(:status AS VARCHAR) IS NULL
                          OR appointment.status = :status
                      )
                      AND (
                          CAST(:pallet_min AS INTEGER) IS NULL
                          OR appointment.pallet_count >= :pallet_min
                      )
                      AND (
                          CAST(:pallet_max AS INTEGER) IS NULL
                          OR appointment.pallet_count <= :pallet_max
                      )
                      AND (
                          CAST(:sku_min AS INTEGER) IS NULL
                          OR appointment.sku_count >= :sku_min
                      )
                      AND (
                          CAST(:sku_max AS INTEGER) IS NULL
                          OR appointment.sku_count <= :sku_max
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
                    COUNT(*)::INTEGER AS appointment_count,
                    COUNT(*) FILTER (
                        WHERE actual_arrival_delay_minutes > 0
                    )::INTEGER AS late_appointments,
                    COUNT(*) FILTER (
                        WHERE actual_turn_time_minutes > sla_minutes
                           OR (
                               actual_turn_time_minutes IS NULL
                               AND predicted_missed = TRUE
                           )
                    )::INTEGER AS sla_risk_or_misses,
                    COUNT(*) FILTER (
                        WHERE turn_risk_score >= 80
                    )::INTEGER AS critical_appointments,
                    ROUND(
                        100.0 * COUNT(*) FILTER (
                            WHERE actual_arrival_delay_minutes > 0
                        ) / NULLIF(COUNT(*), 0),
                        1
                    ) AS late_rate_percent,
                    ROUND(
                        100.0 * COUNT(*) FILTER (
                            WHERE actual_turn_time_minutes > sla_minutes
                               OR (
                                   actual_turn_time_minutes IS NULL
                                   AND predicted_missed = TRUE
                               )
                        ) / NULLIF(COUNT(*), 0),
                        1
                    ) AS sla_miss_rate_percent,
                    ROUND(
                        AVG(actual_arrival_delay_minutes)
                        FILTER (
                            WHERE actual_arrival_delay_minutes IS NOT NULL
                        ),
                        1
                    ) AS average_delay_minutes,
                    ROUND(
                        AVG(actual_turn_time_minutes)
                        FILTER (
                            WHERE actual_turn_time_minutes IS NOT NULL
                        ),
                        1
                    ) AS average_turn_time_minutes,
                    ROUND(
                        AVG(predicted_duration_minutes)
                        FILTER (
                            WHERE predicted_duration_minutes IS NOT NULL
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
                    ROUND(AVG(pallet_count), 1)
                        AS average_pallet_count,
                    ROUND(AVG(sku_count), 1)
                        AS average_sku_count,
                    ROUND(AVG(dock_congestion_percent), 1)
                        AS average_dock_congestion_percent,
                    ROUND(AVG(labor_utilization_percent), 1)
                        AS average_labor_utilization_percent,
                    ROUND(AVG(forklift_utilization_percent), 1)
                        AS average_forklift_utilization_percent,
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
                "pallet_min": pallet_min,
                "pallet_max": pallet_max,
                "sku_min": sku_min,
                "sku_max": sku_max,
                "date_from": date_from,
                "date_to": date_to,
            },
        ).mappings().one()
        return dict(row)

    def advanced_grouped_metrics(
        self,
        *,
        group_by: str,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        product_id: str | None = None,
        appointment_type: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        pallet_min: int | None = None,
        pallet_max: int | None = None,
        sku_min: int | None = None,
        sku_max: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        groups = {
            "facility": (
                "appointment.facility_id",
                "facility.facility_name",
            ),
            "customer": (
                "appointment.customer_id",
                "COALESCE(customer.customer_name, appointment.customer_name)",
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
        if group_by not in groups:
            raise ValueError(
                f"Unsupported analytics grouping: {group_by}"
            )

        group_id, group_label = groups[group_by]
        query = f"""
            WITH latest_prediction AS (
                SELECT DISTINCT ON (prediction.appt_id)
                    prediction.appt_id,
                    prediction.turn_risk_score,
                    prediction.predicted_missed
                FROM appointment_predictions prediction
                ORDER BY
                    prediction.appt_id,
                    prediction.generated_at DESC,
                    prediction.prediction_id DESC
            )
            SELECT
                {group_id} AS group_id,
                {group_label} AS group_label,
                COUNT(DISTINCT appointment.appt_id)::INTEGER
                    AS appointment_count,
                COUNT(DISTINCT appointment.appt_id) FILTER (
                    WHERE appointment.actual_arrival_delay_minutes > 0
                )::INTEGER AS late_appointments,
                COUNT(DISTINCT appointment.appt_id) FILTER (
                    WHERE appointment.actual_turn_time_minutes >
                          appointment.sla_minutes
                       OR prediction.predicted_missed = TRUE
                )::INTEGER AS sla_risk_or_misses,
                COUNT(DISTINCT appointment.appt_id) FILTER (
                    WHERE prediction.turn_risk_score >= 80
                )::INTEGER AS critical_appointments,
                ROUND(
                    100.0
                    * COUNT(DISTINCT appointment.appt_id) FILTER (
                        WHERE appointment.actual_arrival_delay_minutes > 0
                    )
                    / NULLIF(
                        COUNT(DISTINCT appointment.appt_id),
                        0
                    ),
                    1
                ) AS late_rate_percent,
                ROUND(
                    100.0
                    * COUNT(DISTINCT appointment.appt_id) FILTER (
                        WHERE appointment.actual_turn_time_minutes >
                              appointment.sla_minutes
                           OR prediction.predicted_missed = TRUE
                    )
                    / NULLIF(
                        COUNT(DISTINCT appointment.appt_id),
                        0
                    ),
                    1
                ) AS sla_miss_rate_percent,
                ROUND(
                    AVG(appointment.actual_arrival_delay_minutes)
                    FILTER (
                        WHERE appointment.actual_arrival_delay_minutes
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
                        WHERE prediction.turn_risk_score IS NOT NULL
                    ),
                    1
                ) AS average_risk_score,
                ROUND(AVG(appointment.pallet_count), 1)
                    AS average_pallet_count,
                ROUND(AVG(appointment.sku_count), 1)
                    AS average_sku_count,
                ROUND(AVG(allocation.dock_congestion_percent), 1)
                    AS average_dock_congestion_percent,
                ROUND(AVG(allocation.labor_utilization_percent), 1)
                    AS average_labor_utilization_percent,
                ROUND(AVG(allocation.forklift_utilization_percent), 1)
                    AS average_forklift_utilization_percent,
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
            FROM appointments appointment
            LEFT JOIN facilities facility
              ON facility.facility_id = appointment.facility_id
            LEFT JOIN customers customer
              ON customer.customer_id = appointment.customer_id
            LEFT JOIN carriers carrier
              ON carrier.carrier_id = appointment.carrier_id
            LEFT JOIN docks dock
              ON dock.dock_id = appointment.assigned_dock_id
            LEFT JOIN appointment_products line
              ON line.appt_id = appointment.appt_id
            LEFT JOIN products product
              ON product.product_id = line.product_id
            LEFT JOIN appointment_resource_allocations allocation
              ON allocation.appt_id = appointment.appt_id
            LEFT JOIN latest_prediction prediction
              ON prediction.appt_id = appointment.appt_id
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
                  OR appointment.appointment_type = :appointment_type
              )
              AND (
                  CAST(:status AS VARCHAR) IS NULL
                  OR appointment.status = :status
              )
              AND (
                  CAST(:pallet_min AS INTEGER) IS NULL
                  OR appointment.pallet_count >= :pallet_min
              )
              AND (
                  CAST(:pallet_max AS INTEGER) IS NULL
                  OR appointment.pallet_count <= :pallet_max
              )
              AND (
                  CAST(:sku_min AS INTEGER) IS NULL
                  OR appointment.sku_count >= :sku_min
              )
              AND (
                  CAST(:sku_max AS INTEGER) IS NULL
                  OR appointment.sku_count <= :sku_max
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
              AND {group_id} IS NOT NULL
            GROUP BY {group_id}, {group_label}
            LIMIT :limit;
        """

        rows = self.db.execute(
            text(query),
            {
                "facility_id": facility_id,
                "customer_id": customer_id,
                "carrier_id": carrier_id,
                "product_id": product_id,
                "appointment_type": appointment_type,
                "status": status,
                "risk_level": risk_level,
                "pallet_min": pallet_min,
                "pallet_max": pallet_max,
                "sku_min": sku_min,
                "sku_max": sku_max,
                "date_from": date_from,
                "date_to": date_to,
                "limit": min(50, max(1, limit)),
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def resource_effectiveness(
        self,
        *,
        resource_type: str,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        if resource_type not in {"loaders", "forklifts"}:
            raise ValueError(
                f"Unsupported resource type: {resource_type}"
            )
        column = (
            "allocation.actual_loaders"
            if resource_type == "loaders"
            else "allocation.actual_forklifts"
        )
        rows = self.db.execute(
            text(
                f"""
                SELECT
                    {column}::INTEGER AS resource_count,
                    COUNT(*)::INTEGER AS appointment_count,
                    ROUND(
                        AVG(appointment.actual_turn_time_minutes),
                        1
                    ) AS average_turn_time_minutes,
                    ROUND(
                        100.0 * COUNT(*) FILTER (
                            WHERE appointment.actual_sla_missed = TRUE
                        ) / NULLIF(COUNT(*), 0),
                        1
                    ) AS sla_miss_rate_percent,
                    ROUND(AVG(appointment.pallet_count), 1)
                        AS average_pallet_count
                FROM appointments appointment
                JOIN appointment_resource_allocations allocation
                  ON allocation.appt_id = appointment.appt_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND appointment.status = 'Completed'
                  AND appointment.actual_turn_time_minutes IS NOT NULL
                  AND {column} IS NOT NULL
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
                      OR appointment.appointment_type = :appointment_type
                  )
                  AND (
                      CAST(:date_from AS TIMESTAMP) IS NULL
                      OR appointment.scheduled_time >= :date_from
                  )
                  AND (
                      CAST(:date_to AS TIMESTAMP) IS NULL
                      OR appointment.scheduled_time < :date_to
                  )
                GROUP BY {column}
                ORDER BY {column};
                """
            ),
            {
                "facility_id": facility_id,
                "customer_id": customer_id,
                "carrier_id": carrier_id,
                "appointment_type": appointment_type,
                "date_from": date_from,
                "date_to": date_to,
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def turn_time_driver_analysis(
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
        minimum_sample: int = 5,
        limit: int = 8,
    ) -> dict[str, Any]:
        """Compare predefined operational segments with scoped turn-time baseline.

        This is descriptive/associational analysis. It deliberately does not
        claim that any segment causes longer turn time.
        """
        rows = self.db.execute(
            text(
                """
                WITH latest_prediction AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.turn_risk_score,
                        prediction.predicted_delay_minutes
                    FROM appointment_predictions prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                ),
                scoped AS (
                    SELECT
                        appointment.appt_id,
                        appointment.actual_turn_time_minutes,
                        appointment.sla_minutes,
                        appointment.pallet_count,
                        appointment.sku_count,
                        appointment.actual_arrival_delay_minutes,
                        prediction.predicted_delay_minutes,
                        appointment.traffic_severity,
                        appointment.weather_severity,
                        appointment.surge_indicator,
                        allocation.actual_loaders,
                        allocation.actual_forklifts,
                        allocation.dock_congestion_percent,
                        allocation.labor_utilization_percent,
                        allocation.forklift_utilization_percent
                    FROM appointments appointment
                    LEFT JOIN latest_prediction prediction
                      ON prediction.appt_id = appointment.appt_id
                    LEFT JOIN appointment_resource_allocations allocation
                      ON allocation.appt_id = appointment.appt_id
                    WHERE appointment.appt_id LIKE 'DEMO%'
                      AND appointment.actual_turn_time_minutes IS NOT NULL
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
                          OR EXISTS (
                              SELECT 1
                              FROM appointment_products line
                              WHERE line.appt_id = appointment.appt_id
                                AND line.product_id = :product_id
                          )
                      )
                      AND (
                          CAST(:appointment_type AS VARCHAR) IS NULL
                          OR appointment.appointment_type = :appointment_type
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
                ),
                baseline AS (
                    SELECT
                        COUNT(*)::INTEGER AS baseline_appointments,
                        AVG(actual_turn_time_minutes)
                            AS baseline_turn_minutes
                    FROM scoped
                ),
                segment_rows AS (
                    SELECT
                        driver.driver,
                        scoped.actual_turn_time_minutes,
                        scoped.sla_minutes
                    FROM scoped
                    CROSS JOIN LATERAL (
                        VALUES
                            (
                                'Large pallet volume (30+ pallets)',
                                scoped.pallet_count >= 30
                            ),
                            (
                                'High SKU complexity (10+ SKUs)',
                                scoped.sku_count >= 10
                            ),
                            (
                                'Dock congestion (60%+)',
                                scoped.dock_congestion_percent >= 60
                            ),
                            (
                                'High labor utilization (80%+)',
                                scoped.labor_utilization_percent >= 80
                            ),
                            (
                                'High forklift utilization (80%+)',
                                scoped.forklift_utilization_percent >= 80
                            ),
                            (
                                'Late arrival',
                                scoped.actual_arrival_delay_minutes > 0
                            ),
                            (
                                'Predicted arrival delay',
                                scoped.predicted_delay_minutes > 0
                            ),
                            (
                                'High traffic severity',
                                scoped.traffic_severity >= 3
                            ),
                            (
                                'Adverse weather',
                                scoped.weather_severity >= 2
                            ),
                            (
                                'Surge-volume condition',
                                scoped.surge_indicator = TRUE
                            ),
                            (
                                '3+ loaders allocated',
                                scoped.actual_loaders >= 3
                            ),
                            (
                                '2+ forklifts allocated',
                                scoped.actual_forklifts >= 2
                            )
                    ) AS driver(driver, matches)
                    WHERE driver.matches
                ),
                aggregated AS (
                    SELECT
                        segment_rows.driver,
                        COUNT(*)::INTEGER AS appointment_count,
                        AVG(segment_rows.actual_turn_time_minutes)
                            AS segment_turn_minutes,
                        100.0 * COUNT(*) FILTER (
                            WHERE segment_rows.actual_turn_time_minutes >
                                  segment_rows.sla_minutes
                        ) / NULLIF(COUNT(*), 0)
                            AS sla_miss_rate_percent
                    FROM segment_rows
                    GROUP BY segment_rows.driver
                )
                SELECT
                    aggregated.driver,
                    baseline.baseline_appointments,
                    ROUND(
                        baseline.baseline_turn_minutes,
                        1
                    ) AS baseline_turn_minutes,
                    aggregated.appointment_count,
                    ROUND(
                        100.0 * aggregated.appointment_count
                        / NULLIF(
                            baseline.baseline_appointments,
                            0
                        ),
                        1
                    ) AS scope_share_percent,
                    ROUND(
                        aggregated.segment_turn_minutes,
                        1
                    ) AS segment_turn_minutes,
                    ROUND(
                        aggregated.segment_turn_minutes
                        - baseline.baseline_turn_minutes,
                        1
                    ) AS turn_time_delta_minutes,
                    ROUND(
                        aggregated.sla_miss_rate_percent,
                        1
                    ) AS sla_miss_rate_percent
                FROM aggregated
                CROSS JOIN baseline
                WHERE aggregated.appointment_count >= :minimum_sample
                ORDER BY
                    turn_time_delta_minutes DESC,
                    aggregated.appointment_count DESC
                LIMIT :limit;
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
                "minimum_sample": max(1, minimum_sample),
                "limit": min(20, max(1, limit)),
            },
        ).mappings().all()

        driver_rows = [dict(row) for row in rows]
        if driver_rows:
            return {
                "baseline_appointments": int(
                    driver_rows[0].get("baseline_appointments") or 0
                ),
                "baseline_turn_minutes": driver_rows[0].get(
                    "baseline_turn_minutes"
                ),
                "drivers": driver_rows,
            }

        # Preserve the baseline even when no segment survives the reliability
        # threshold, so the Copilot can distinguish "no records" from
        # "records exist but no reliable positive driver".
        baseline = self.db.execute(
            text(
                """
                WITH latest_prediction AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.turn_risk_score
                    FROM appointment_predictions prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                )
                SELECT
                    COUNT(*)::INTEGER AS baseline_appointments,
                    ROUND(
                        AVG(appointment.actual_turn_time_minutes),
                        1
                    ) AS baseline_turn_minutes
                FROM appointments appointment
                LEFT JOIN latest_prediction prediction
                  ON prediction.appt_id = appointment.appt_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND appointment.actual_turn_time_minutes IS NOT NULL
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
                      OR EXISTS (
                          SELECT 1
                          FROM appointment_products line
                          WHERE line.appt_id = appointment.appt_id
                            AND line.product_id = :product_id
                      )
                  )
                  AND (
                      CAST(:appointment_type AS VARCHAR) IS NULL
                      OR appointment.appointment_type = :appointment_type
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
                  );
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

        return {
            "baseline_appointments": int(
                baseline.get("baseline_appointments") or 0
            ),
            "baseline_turn_minutes": baseline.get(
                "baseline_turn_minutes"
            ),
            "drivers": [],
        }

    def risk_driver_summary(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                WITH latest_prediction AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.predicted_missed,
                        prediction.predicted_delay_minutes
                    FROM appointment_predictions prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                ),
                risky AS (
                    SELECT
                        appointment.traffic_severity,
                        appointment.weather_severity,
                        appointment.pallet_count,
                        appointment.sku_count,
                        prediction.predicted_delay_minutes,
                        allocation.dock_congestion_percent,
                        allocation.labor_utilization_percent,
                        allocation.forklift_utilization_percent
                    FROM appointments appointment
                    JOIN latest_prediction prediction
                      ON prediction.appt_id = appointment.appt_id
                    LEFT JOIN appointment_resource_allocations allocation
                      ON allocation.appt_id = appointment.appt_id
                    WHERE appointment.appt_id LIKE 'DEMO%'
                      AND prediction.predicted_missed = TRUE
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
                          OR appointment.appointment_type = :appointment_type
                      )
                      AND (
                          CAST(:date_from AS TIMESTAMP) IS NULL
                          OR appointment.scheduled_time >= :date_from
                      )
                      AND (
                          CAST(:date_to AS TIMESTAMP) IS NULL
                          OR appointment.scheduled_time < :date_to
                      )
                ),
                drivers AS (
                    SELECT 'High traffic' AS driver,
                           COUNT(*) FILTER (WHERE traffic_severity >= 3) AS affected
                    FROM risky
                    UNION ALL
                    SELECT 'Adverse weather',
                           COUNT(*) FILTER (WHERE weather_severity >= 2)
                    FROM risky
                    UNION ALL
                    SELECT 'Dock congestion',
                           COUNT(*) FILTER (WHERE dock_congestion_percent >= 60)
                    FROM risky
                    UNION ALL
                    SELECT 'High labor utilization',
                           COUNT(*) FILTER (WHERE labor_utilization_percent >= 80)
                    FROM risky
                    UNION ALL
                    SELECT 'High forklift utilization',
                           COUNT(*) FILTER (WHERE forklift_utilization_percent >= 80)
                    FROM risky
                    UNION ALL
                    SELECT 'Large pallet volume',
                           COUNT(*) FILTER (WHERE pallet_count >= 30)
                    FROM risky
                    UNION ALL
                    SELECT 'High SKU complexity',
                           COUNT(*) FILTER (WHERE sku_count >= 10)
                    FROM risky
                    UNION ALL
                    SELECT 'Predicted arrival delay',
                           COUNT(*) FILTER (WHERE predicted_delay_minutes > 0)
                    FROM risky
                )
                SELECT
                    driver,
                    affected::INTEGER AS affected_appointments
                FROM drivers
                WHERE affected > 0
                ORDER BY affected DESC, driver
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
                "limit": min(12, max(1, limit)),
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def mission_summary(
        self,
        *,
        facility_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        return dict(
            self.db.execute(
                text(
                    """
                    SELECT
                        COUNT(*)::INTEGER AS mission_count,
                        COUNT(*) FILTER (
                            WHERE status = 'Proposed'
                        )::INTEGER AS proposed,
                        COUNT(*) FILTER (
                            WHERE status = 'Accepted'
                        )::INTEGER AS accepted,
                        COUNT(*) FILTER (
                            WHERE status = 'In Progress'
                        )::INTEGER AS in_progress,
                        COUNT(*) FILTER (
                            WHERE status = 'Completed'
                        )::INTEGER AS completed,
                        COALESCE(
                            SUM(estimated_net_savings),
                            0
                        ) AS projected_net_savings,
                        COALESCE(
                            SUM(realized_net_savings)
                            FILTER (
                                WHERE realized_net_savings IS NOT NULL
                            ),
                            0
                        ) AS realized_net_savings,
                        COALESCE(
                            SUM(realized_minutes_saved)
                            FILTER (
                                WHERE realized_minutes_saved IS NOT NULL
                            ),
                            0
                        ) AS realized_minutes_saved
                    FROM optimization_missions
                    WHERE (
                        CAST(:facility_id AS VARCHAR) IS NULL
                        OR facility_id = :facility_id
                    )
                      AND (
                        CAST(:date_from AS TIMESTAMP) IS NULL
                        OR created_at >= :date_from
                      )
                      AND (
                        CAST(:date_to AS TIMESTAMP) IS NULL
                        OR created_at < :date_to
                      );
                    """
                ),
                {
                    "facility_id": facility_id,
                    "date_from": date_from,
                    "date_to": date_to,
                },
            ).mappings().one()
        )

    def action_effectiveness(
        self,
        *,
        facility_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    action_signature,
                    SUM(sample_size)::INTEGER AS sample_size,
                    ROUND(
                        SUM(sla_success_rate * sample_size)
                        / NULLIF(SUM(sample_size), 0)
                        * 100,
                        1
                    ) AS sla_success_percent,
                    ROUND(
                        SUM(
                            avg_realized_minutes_saved * sample_size
                        ) / NULLIF(SUM(sample_size), 0),
                        1
                    ) AS avg_realized_minutes_saved,
                    ROUND(
                        SUM(
                            avg_realized_net_savings * sample_size
                        ) / NULLIF(SUM(sample_size), 0),
                        2
                    ) AS avg_realized_net_savings
                FROM optimization_action_effectiveness
                WHERE (
                    CAST(:facility_id AS VARCHAR) IS NULL
                    OR facility_id = :facility_id
                )
                GROUP BY action_signature
                ORDER BY
                    avg_realized_minutes_saved DESC,
                    sample_size DESC
                LIMIT :limit;
                """
            ),
            {
                "facility_id": facility_id,
                "limit": min(25, max(1, limit)),
            },
        ).mappings().all()
        return [dict(row) for row in rows]

    def product_handling_metrics(
        self,
        *,
        facility_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                WITH latest_history AS (
                    SELECT DISTINCT ON (
                        history.facility_id,
                        history.product_id
                    )
                        history.facility_id,
                        history.product_id,
                        history.avg_minutes_per_pallet,
                        history.avg_loaders,
                        history.avg_forklifts,
                        history.sla_success_rate,
                        history.as_of_date
                    FROM product_handling_history history
                    WHERE (
                        CAST(:facility_id AS VARCHAR) IS NULL
                        OR history.facility_id = :facility_id
                    )
                    ORDER BY
                        history.facility_id,
                        history.product_id,
                        history.as_of_date DESC
                )
                SELECT
                    product.product_id,
                    product.product_name,
                    ROUND(
                        AVG(latest_history.avg_minutes_per_pallet),
                        2
                    ) AS minutes_per_pallet,
                    ROUND(
                        AVG(latest_history.avg_loaders),
                        2
                    ) AS avg_loaders,
                    ROUND(
                        AVG(latest_history.avg_forklifts),
                        2
                    ) AS avg_forklifts,
                    ROUND(
                        AVG(latest_history.sla_success_rate) * 100,
                        1
                    ) AS sla_success_percent
                FROM latest_history
                JOIN products product
                  ON product.product_id = latest_history.product_id
                GROUP BY
                    product.product_id,
                    product.product_name
                ORDER BY minutes_per_pallet DESC
                LIMIT :limit;
                """
            ),
            {
                "facility_id": facility_id,
                "limit": min(25, max(1, limit)),
            },
        ).mappings().all()
        return [dict(row) for row in rows]
