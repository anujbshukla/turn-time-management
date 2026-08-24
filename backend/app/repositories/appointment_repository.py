from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import Appointment
from app.repositories.outcome_rules import outcome_filter_sql
from app.services.appointment_explainability import (
    build_action_rationale,
    build_risk_contributors,
    build_sla_outcome_reason,
)


class AppointmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        assigned_dock_id: str | None = None,
        appointment_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        pallet_min: int | None = None,
        pallet_max: int | None = None,
        sku_min: int | None = None,
        sku_max: int | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        outcome: str | None = None,
        search: str | None = None,
        sort_by: str | None = None,
        sort_direction: str | None = None,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size
        shared_outcome_filter = outcome_filter_sql("a")

        sort_expressions = {
            "appt_id": "a.appt_id",
            "customer_name": "a.customer_name",
            "facility_name": "f.facility_name",
            "carrier_name": "c.carrier_name",
            "scheduled_time": "a.scheduled_time",
            "estimated_arrival_time": "a.estimated_arrival_time",
            "status": (
                "CASE a.status "
                "WHEN 'Scheduled' THEN 1 "
                "WHEN 'En Route' THEN 2 "
                "WHEN 'Arrived' THEN 3 "
                "WHEN 'Waiting' THEN 4 "
                "WHEN 'Dock Assigned' THEN 5 "
                "WHEN 'In Progress' THEN 6 "
                "WHEN 'Completed' THEN 7 "
                "ELSE 99 END"
            ),
            "turn_risk_score": "p.turn_risk_score",
        }

        direction = (sort_direction or "").lower()
        if sort_by in sort_expressions and direction in {"asc", "desc"}:
            nulls = "NULLS LAST"
            order_by_clause = (
                f"{sort_expressions[sort_by]} {direction.upper()} {nulls}, "
                "a.appt_id ASC"
            )
        else:
            order_by_clause = (
                "CASE a.status "
                "WHEN 'In Progress' THEN 1 "
                "WHEN 'Dock Assigned' THEN 2 "
                "WHEN 'Waiting' THEN 3 "
                "WHEN 'Arrived' THEN 4 "
                "WHEN 'En Route' THEN 5 "
                "WHEN 'Scheduled' THEN 6 "
                "WHEN 'Completed' THEN 7 "
                "ELSE 8 "
                "END ASC, "

                "CASE "
                "WHEN a.status IN ('En Route', 'Scheduled') "
                "THEN ABS(EXTRACT(EPOCH FROM ("
                "a.estimated_arrival_time - "
                "(CURRENT_TIMESTAMP AT TIME ZONE "
                "COALESCE(NULLIF(f.timezone, ''), 'America/New_York'))"
                "))) "
                "ELSE NULL "
                "END ASC NULLS LAST, "

                "a.scheduled_time ASC, "
                "a.appt_id ASC"
            )

        parameters = {
            "page_size": page_size,
            "offset": offset,
            "facility_id": facility_id,
            "customer_id": customer_id,
            "carrier_id": carrier_id,
            "assigned_dock_id": assigned_dock_id,
            "appointment_type": appointment_type,
            "date_from": date_from,
            "date_to": date_to,
            "pallet_min": pallet_min,
            "pallet_max": pallet_max,
            "sku_min": sku_min,
            "sku_max": sku_max,
            "status": status,
            "risk_level": risk_level,
            "outcome": outcome,
            "search": (
                f"%{search.strip()}%"
                if search
                else None
            ),
        }

        rows = self.db.execute(
            text(
                """
                SELECT
                    a.appt_id,
                    a.customer_name,
                    a.customer_id,
                    a.facility_id,
                    f.facility_name,
                    a.carrier_id,
                    c.carrier_name,
                    a.scheduled_time,
                    a.estimated_arrival_time,
                    a.actual_arrival_time,
                    a.assigned_dock_id,
                    d.dock_name,
                    a.status,
                    a.original_scheduled_time,
                    a.is_rescheduled,
                    a.reschedule_count,
                    a.rescheduled_at,
                    a.edit_count,
                    a.last_edited_at,
                    a.pallet_count,
                    a.sku_count,
                    a.priority,
                    a.sla_minutes,
                    a.actual_arrival_delay_minutes,
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

                LEFT JOIN LATERAL (
                    SELECT
                        predicted_duration_minutes,
                        turn_risk_score,
                        sla_recovery_probability,
                        predicted_missed
                    FROM appointment_predictions
                    WHERE appt_id = a.appt_id
                    ORDER BY generated_at DESC
                    LIMIT 1
                ) p ON TRUE

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

                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR a.facility_id = CAST(:facility_id AS VARCHAR)
                  )


                  AND (
                      CAST(:customer_id AS VARCHAR) IS NULL
                      OR a.customer_id = CAST(:customer_id AS VARCHAR)
                  )

                  AND (
                      CAST(:carrier_id AS VARCHAR) IS NULL
                      OR a.carrier_id = CAST(:carrier_id AS VARCHAR)
                  )
                    AND (
                        CAST(:assigned_dock_id AS VARCHAR) IS NULL
                        OR a.assigned_dock_id = CAST(:assigned_dock_id AS VARCHAR)
                    )
                  AND (
                      CAST(:appointment_type AS VARCHAR) IS NULL
                      OR LOWER(a.appointment_type) =
                         LOWER(CAST(:appointment_type AS VARCHAR))
                  )

                  AND (
                      CAST(:date_from AS DATE) IS NULL
                      OR a.scheduled_time >= CAST(:date_from AS DATE)
                  )

                  AND (
                      CAST(:date_to AS DATE) IS NULL
                      OR a.scheduled_time < CAST(:date_to AS DATE)
                  )
                  AND (
      CAST(:pallet_min AS INTEGER) IS NULL
      OR a.pallet_count >= CAST(:pallet_min AS INTEGER)
)

AND (
      CAST(:pallet_max AS INTEGER) IS NULL
      OR a.pallet_count <= CAST(:pallet_max AS INTEGER)
)

AND (
      CAST(:sku_min AS INTEGER) IS NULL
      OR a.sku_count >= CAST(:sku_min AS INTEGER)
)

AND (
      CAST(:sku_max AS INTEGER) IS NULL
      OR a.sku_count <= CAST(:sku_max AS INTEGER)
)
                  AND (
                      CAST(:status AS VARCHAR) IS NULL
                      OR a.status = CAST(:status AS VARCHAR)
                  )

                  AND (
                      CAST(:search AS VARCHAR) IS NULL
                      OR a.appt_id ILIKE CAST(:search AS VARCHAR)
                      OR a.customer_name ILIKE CAST(:search AS VARCHAR)
                      OR c.carrier_name ILIKE CAST(:search AS VARCHAR)
                  )

                  AND (
                      CAST(:risk_level AS VARCHAR) IS NULL

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'Low'
                          AND p.turn_risk_score < 30
                      )

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'Medium'
                          AND p.turn_risk_score >= 30
                          AND p.turn_risk_score < 60
                      )

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'High'
                          AND p.turn_risk_score >= 60
                          AND p.turn_risk_score < 80
                      )

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'Critical'
                          AND p.turn_risk_score >= 80
                      )
                  )

                  {shared_outcome_filter}

                ORDER BY
                    {order_by_clause}

                LIMIT :page_size
                OFFSET :offset;
                """.format(
                    order_by_clause=order_by_clause,
                    shared_outcome_filter=shared_outcome_filter,
                )
            ),
            parameters,
        ).mappings().all()

        total = self.db.execute(
            text(
                """
                SELECT COUNT(*)

                FROM appointments a

                LEFT JOIN carriers c
                    ON c.carrier_id = a.carrier_id

                LEFT JOIN LATERAL (
                    SELECT turn_risk_score
                    FROM appointment_predictions
                    WHERE appt_id = a.appt_id
                    ORDER BY generated_at DESC
                    LIMIT 1
                ) p ON TRUE

                WHERE a.appt_id LIKE 'DEMO%'

                  AND (
                      CAST(:facility_id AS VARCHAR) IS NULL
                      OR a.facility_id = CAST(:facility_id AS VARCHAR)
                  )


                  AND (
                      CAST(:customer_id AS VARCHAR) IS NULL
                      OR a.customer_id = CAST(:customer_id AS VARCHAR)
                  )

                  AND (
                      CAST(:carrier_id AS VARCHAR) IS NULL
                      OR a.carrier_id = CAST(:carrier_id AS VARCHAR)
                  )
                    AND (
                        CAST(:assigned_dock_id AS VARCHAR) IS NULL
                        OR a.assigned_dock_id = CAST(:assigned_dock_id AS VARCHAR)
                    )
                  AND (
                      CAST(:appointment_type AS VARCHAR) IS NULL
                      OR LOWER(a.appointment_type) =
                         LOWER(CAST(:appointment_type AS VARCHAR))
                  )

                  AND (
                      CAST(:date_from AS DATE) IS NULL
                      OR a.scheduled_time >= CAST(:date_from AS DATE)
                  )

                  AND (
                      CAST(:date_to AS DATE) IS NULL
                      OR a.scheduled_time < CAST(:date_to AS DATE)
                  )
AND (
      CAST(:pallet_min AS INTEGER) IS NULL
      OR a.pallet_count >= CAST(:pallet_min AS INTEGER)
)

AND (
      CAST(:pallet_max AS INTEGER) IS NULL
      OR a.pallet_count <= CAST(:pallet_max AS INTEGER)
)

AND (
      CAST(:sku_min AS INTEGER) IS NULL
      OR a.sku_count >= CAST(:sku_min AS INTEGER)
)

AND (
      CAST(:sku_max AS INTEGER) IS NULL
      OR a.sku_count <= CAST(:sku_max AS INTEGER)
)
                  AND (
                      CAST(:status AS VARCHAR) IS NULL
                      OR a.status = CAST(:status AS VARCHAR)
                  )

                  AND (
                      CAST(:search AS VARCHAR) IS NULL
                      OR a.appt_id ILIKE CAST(:search AS VARCHAR)
                      OR a.customer_name ILIKE CAST(:search AS VARCHAR)
                      OR c.carrier_name ILIKE CAST(:search AS VARCHAR)
                  )

                  AND (
                      CAST(:risk_level AS VARCHAR) IS NULL

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'Low'
                          AND p.turn_risk_score < 30
                      )

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'Medium'
                          AND p.turn_risk_score >= 30
                          AND p.turn_risk_score < 60
                      )

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'High'
                          AND p.turn_risk_score >= 60
                          AND p.turn_risk_score < 80
                      )

                      OR (
                          CAST(:risk_level AS VARCHAR) = 'Critical'
                          AND p.turn_risk_score >= 80
                      )
                  )

                  {shared_outcome_filter};
                """.format(
                    shared_outcome_filter=shared_outcome_filter,
                )
            ),
            parameters,
        ).scalar_one()

        total_pages = max(
            1,
            (total + page_size - 1) // page_size,
        )

        return {
            "items": [
                dict(row)
                for row in rows
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": page < total_pages,
            },
        }

    def _ensure_recovery_plan_for_at_risk_appointment(
        self,
        *,
        appointment: dict[str, Any],
        prediction: dict[str, Any] | None,
        recommendation: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Create a structured recovery plan only when an active at-risk
        appointment has no recommendation actions.

        This deliberately reuses create_initial_recommendation(), which is
        already part of this repository and writes to the existing
        appointment_recommendations / recommendation_actions schema.
        """
        if prediction is None:
            return recommendation

        if appointment.get("status") == "Completed":
            return recommendation

        predicted_delay = max(
            0,
            int(prediction.get("predicted_delay_minutes") or 0),
        )
        predicted_duration = max(
            0,
            int(prediction.get("predicted_duration_minutes") or 0),
        )
        predicted_turn_time = predicted_delay + predicted_duration
        risk_score = int(prediction.get("turn_risk_score") or 0)
        predicted_missed = bool(prediction.get("predicted_missed"))
        sla_minutes = int(appointment.get("sla_minutes") or 120)

        is_at_risk = (
            risk_score >= 60
            or predicted_missed
            or predicted_turn_time > sla_minutes
        )
        if not is_at_risk:
            return recommendation

        if recommendation is not None:
            action_count = self.db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM recommendation_actions
                    WHERE recommendation_id = :recommendation_id;
                    """
                ),
                {
                    "recommendation_id":
                        recommendation["recommendation_id"],
                },
            ).scalar_one()

            if int(action_count or 0) > 0:
                return recommendation

        # Create a new latest recommendation with structured actions.
        # Use total predicted turn time (delay + service duration) so the
        # recovery plan reflects the full SLA exposure.
        self.create_initial_recommendation(
            appt_id=appointment["appt_id"],
            dock_id=appointment.get("assigned_dock_id"),
            predicted_duration_minutes=predicted_turn_time,
            sla_minutes=sla_minutes,
            detention_cost_per_hour=float(
                appointment.get("detention_cost_per_hour") or 0
            ),
        )

        refreshed = self.db.execute(
            text(
                """
                SELECT
                    recommendation_id,
                    recommendation_type,
                    recommended_action,
                    recommended_dock_id,
                    recommended_sequence,
                    additional_labor,
                    estimated_loss_without_action,
                    estimated_cost_of_action,
                    estimated_savings,
                    status,
                    created_at,
                    responded_at,
                    responded_by
                FROM appointment_recommendations
                WHERE appt_id = :appt_id
                ORDER BY created_at DESC
                LIMIT 1;
                """
            ),
            {"appt_id": appointment["appt_id"]},
        ).mappings().one_or_none()

        return dict(refreshed) if refreshed is not None else recommendation

    def get_details(
        self,
        appt_id: str,
    ) -> dict[str, Any] | None:
        appointment = self.db.execute(
            text(
                """
                SELECT
                    a.appt_id,
                    a.appt_date,
                    a.customer_id,
                    a.customer_name,
                    customer.industry
                        AS customer_industry,
                    customer.priority_tier,
                    customer.annual_revenue,

                    a.facility_id,
                    facility.facility_name,
                    facility.timezone,

                    a.carrier_id,
                    carrier.carrier_name,

                    a.assigned_dock_id,
                    dock.dock_name,
                    dock.dock_type,
                    dock.temperature_zone
                        AS dock_temperature_zone,

                    a.scheduled_time,
                    a.estimated_arrival_time,
                    a.actual_arrival_time,
                    a.actual_loading_start_time,
                    a.actual_loading_end_time,
                    a.actual_departure_time,

                    a.status,
                    a.original_scheduled_time,
                    a.is_rescheduled,
                    a.reschedule_count,
                    a.rescheduled_at,
                    a.edit_count,
                    a.last_edited_at,
                    a.appointment_type,
                    a.load_type,
                    a.trailer_number,
                    driver.driver_name,
                    driver.license_number,
                    driver.license_state,
                    driver.phone_number AS driver_phone,
                    driver.tractor_number,
                    a.origin_name,
                    a.origin_city,
                    a.origin_state,
                    a.destination_name,
                    a.destination_city,
                    a.destination_state,

                    a.pallet_count,
                    a.sku_count,
                    a.total_weight,
                    a.total_cube,
                    a.priority,
                    a.sla_minutes,
                    a.detention_cost_per_hour,

                    a.actual_arrival_delay_minutes,
                    a.actual_loading_duration_minutes,
                    a.actual_turn_time_minutes,
                    a.actual_sla_missed,

                    a.distance_band,
                    a.traffic_severity,
                    a.weather_severity,
                    a.surge_indicator

                FROM appointments a

                JOIN facilities facility
                    ON facility.facility_id =
                        a.facility_id

                LEFT JOIN carriers carrier
                    ON carrier.carrier_id =
                        a.carrier_id

                LEFT JOIN docks dock
                    ON dock.dock_id =
                        a.assigned_dock_id

                LEFT JOIN customers customer
                    ON customer.customer_id =
                        a.customer_id

                LEFT JOIN appointment_drivers driver
                    ON driver.appt_id = a.appt_id

                WHERE a.appt_id = :appt_id;
                """
            ),
            {"appt_id": appt_id},
        ).mappings().one_or_none()

        if appointment is None:
            return None

        products = self.db.execute(
            text(
                """
                SELECT
                    product.product_id,
                    product.sku,
                    product.product_name,
                    product.category,
                    product.temperature_zone,
                    product.handling_type,
                    product.unit_of_measure,
                    product.unit_weight_lb,
                    product.length_in,
                    product.width_in,
                    product.height_in,
                    product.unit_volume_cuft,
                    line.quantity,
                    line.case_count,
                    line.pallet_count,
                    line.line_weight_lb,
                    line.line_volume_cuft

                FROM appointment_products line

                JOIN products product
                    ON product.product_id =
                        line.product_id

                WHERE line.appt_id = :appt_id

                ORDER BY
                    line.pallet_count DESC,
                    product.product_name;
                """
            ),
            {"appt_id": appt_id},
        ).mappings().all()

        # Original operational appointment events.
        appointment_events = self.db.execute(
            text(
                """
                SELECT
                    event_id,
                    event_type,
                    event_time,
                    notes,
                    performed_by,
                    field_name,
                    old_value,
                    new_value,
                    details_json

                FROM appointment_events

                WHERE appt_id = :appt_id

                ORDER BY event_time;
                """
            ),
            {"appt_id": appt_id},
        ).mappings().all()

        # Recovery-action decisions become timeline events.
        decision_events = self.db.execute(
            text(
                """
                SELECT
                    action.recommendation_action_id
                        AS event_id,

                    CASE
                        WHEN action.decision_status =
                            'Accepted'
                            THEN
                                'RECOVERY_ACTION_ACCEPTED'

                        WHEN action.decision_status =
                            'Rejected'
                            THEN
                                'RECOVERY_ACTION_REJECTED'

                        ELSE
                            'RECOVERY_ACTION_RESET'
                    END AS event_type,

                    action.decision_at
                        AS event_time,

                    CONCAT(
                        action.action_title,

                        CASE
                            WHEN action.decision_by
                                IS NOT NULL
                                AND action.decision_by <> ''
                                THEN CONCAT(
                                    ' by ',
                                    action.decision_by
                                )
                            ELSE ''
                        END,

                        CASE
                            WHEN action.decision_notes
                                IS NOT NULL
                                AND action.decision_notes <> ''
                                THEN CONCAT(
                                    '. Notes: ',
                                    action.decision_notes
                                )
                            ELSE ''
                        END
                    ) AS notes,

                    action.decision_by AS performed_by,
                    'recommendation_action' AS field_name,
                    NULL::TEXT AS old_value,
                    action.decision_status AS new_value,
                    jsonb_build_object(
                        'action_id', action.recommendation_action_id,
                        'action_code', action.action_code,
                        'action_title', action.action_title,
                        'minutes_saved', action.estimated_minutes_saved,
                        'decision_notes', action.decision_notes
                    ) AS details_json

                FROM recommendation_actions action

                JOIN appointment_recommendations
                    recommendation
                    ON recommendation.recommendation_id =
                        action.recommendation_id

                WHERE recommendation.appt_id =
                    :appt_id

                AND action.decision_at
                    IS NOT NULL

                ORDER BY action.decision_at;
                """
            ),
            {"appt_id": appt_id},
        ).mappings().all()

        prediction = self.db.execute(
            text(
                """
                SELECT
                    prediction_id,
                    predicted_arrival_time,
                    predicted_delay_minutes,
                    predicted_duration_minutes,
                    sla_miss_probability,
                    sla_recovery_probability,
                    turn_risk_score,
                    predicted_missed,
                    model_version,
                    generated_at

                FROM appointment_predictions

                WHERE appt_id = :appt_id

                ORDER BY generated_at DESC

                LIMIT 1;
                """
            ),
            {"appt_id": appt_id},
        ).mappings().one_or_none()

        recommendation = self.db.execute(
            text(
                """
                SELECT
                    recommendation_id,
                    recommendation_type,
                    recommended_action,
                    recommended_dock_id,
                    recommended_sequence,
                    additional_labor,
                    estimated_loss_without_action,
                    estimated_cost_of_action,
                    estimated_savings,
                    status,
                    created_at,
                    responded_at,
                    responded_by

                FROM appointment_recommendations

                WHERE appt_id = :appt_id

                ORDER BY created_at DESC

                LIMIT 1;
                """
            ),
            {"appt_id": appt_id},
        ).mappings().one_or_none()

        appointment_dict = dict(appointment)

        prediction_dict = (
            dict(prediction)
            if prediction is not None
            else None
        )

        recommendation_dict = (
            dict(recommendation)
            if recommendation is not None
            else None
        )

        recommendation_dict = self._ensure_recovery_plan_for_at_risk_appointment(
            appointment=appointment_dict,
            prediction=prediction_dict,
            recommendation=recommendation_dict,
        )
        recommendation = recommendation_dict

        actions: list[dict[str, Any]] = []

        if recommendation is not None:
            action_rows = self.db.execute(
                text(
                    """
                    SELECT
                        recommendation_action_id,
                        sequence_number,
                        action_code,
                        action_title,
                        action_description,
                        owner_role,
                        start_by,
                        estimated_minutes_saved,
                        additional_loaders,
                        additional_forklifts,
                        required_equipment_type,
                        required_dock_id,
                        estimated_action_cost,
                        status,
                        decision_status,
                        decision_at,
                        decision_by,
                        decision_notes

                    FROM recommendation_actions

                    WHERE recommendation_id =
                        :recommendation_id

                    ORDER BY sequence_number;
                    """
                ),
                {
                    "recommendation_id":
                        recommendation[
                            "recommendation_id"
                        ],
                },
            ).mappings().all()

            actions = [dict(row) for row in action_rows]
            for action in actions:
                action["recommendation_reason"] = build_action_rationale(
                    action, appointment_dict, prediction_dict
                )

        # Merge original operational events with
        # recovery-action decision events.
        combined_events = [
            dict(row)
            for row in appointment_events
        ]

        combined_events.extend(
            dict(row)
            for row in decision_events
        )

        # Sort chronologically. Null event times, if any,
        # appear at the end.
        combined_events.sort(
            key=lambda event: (
                event["event_time"] is None,
                event["event_time"],
            )
        )

        proposed_minutes_saved = sum(
            action["estimated_minutes_saved"] or 0
            for action in actions
        )

        accepted_minutes_saved = sum(
            action["estimated_minutes_saved"] or 0
            for action in actions
            if action.get("decision_status")
            == "Accepted"
        )

        rejected_minutes_saved = sum(
            action["estimated_minutes_saved"] or 0
            for action in actions
            if action.get("decision_status")
            == "Rejected"
        )

        pending_minutes_saved = sum(
            action["estimated_minutes_saved"] or 0
            for action in actions
            if action.get("decision_status")
            == "Pending"
        )

        accepted_action_cost = sum(
            action["estimated_action_cost"] or 0
            for action in actions
            if action.get("decision_status")
            == "Accepted"
        )

        predicted_turn_time = None
        accepted_projected_turn_time = None
        proposed_projected_turn_time = None

        if prediction_dict is not None:
            predicted_delay = (
                prediction_dict[
                    "predicted_delay_minutes"
                ]
                or 0
            )

            predicted_duration = (
                prediction_dict[
                    "predicted_duration_minutes"
                ]
                or 0
            )

            predicted_turn_time = (
                max(0, predicted_delay)
                + predicted_duration
            )

            accepted_projected_turn_time = max(
                0,
                predicted_turn_time
                - accepted_minutes_saved,
            )

            proposed_projected_turn_time = max(
                0,
                predicted_turn_time
                - proposed_minutes_saved,
            )

        sla_minutes = appointment_dict[
            "sla_minutes"
        ]

        proposed_sla_recovered = (
            proposed_projected_turn_time
            is not None
            and proposed_projected_turn_time
            <= sla_minutes
        )

        accepted_sla_recovered = (
            accepted_projected_turn_time
            is not None
            and accepted_projected_turn_time
            <= sla_minutes
        )

        accepted_actions = [
            action
            for action in actions
            if action.get("decision_status") == "Accepted"
        ]

        is_completed = (
            appointment_dict.get("status") == "Completed"
        )
        actual_turn_time = appointment_dict.get(
            "actual_turn_time_minutes"
        )
        actual_arrival_delay = (
            appointment_dict.get(
                "actual_arrival_delay_minutes"
            )
            or 0
        )
        was_late = actual_arrival_delay > 0
        recommendation_used = bool(accepted_actions) or (
            recommendation_dict is not None
            and recommendation_dict.get("status")
            in {"Accepted", "Completed"}
        )

        actual_sla_met = (
            is_completed
            and actual_turn_time is not None
            and actual_turn_time <= sla_minutes
        )
        actual_sla_missed = (
            is_completed
            and (
                (
                    actual_turn_time is not None
                    and actual_turn_time > sla_minutes
                )
                or (
                    actual_turn_time is None
                    and appointment_dict.get(
                        "actual_sla_missed"
                    )
                    is True
                )
            )
        )

        completed_outcome = "Not completed"
        if is_completed:
            if actual_sla_missed:
                completed_outcome = "Missed SLA"
            elif was_late and actual_sla_met:
                completed_outcome = (
                    "Recovered with recommendations"
                    if recommendation_used
                    else "Recovered without recommendations"
                )
            elif actual_sla_met:
                completed_outcome = "Completed within SLA"
            else:
                completed_outcome = "Completed outcome unavailable"

        sla_variance_minutes = (
            actual_turn_time - sla_minutes
            if actual_turn_time is not None
            else None
        )

        risk_contributors = build_risk_contributors(appointment_dict, prediction_dict)
        sla_outcome_status, sla_outcome_reason = build_sla_outcome_reason(
            appointment_dict,
            recommendation_used=recommendation_used,
            accepted_minutes_saved=accepted_minutes_saved,
            actual_sla_met=actual_sla_met,
            actual_sla_missed=actual_sla_missed,
            was_late=was_late,
            sla_variance_minutes=sla_variance_minutes,
        )

        return {
            "appointment": appointment_dict,

            "products": [
                dict(row)
                for row in products
            ],

            # Returns both operational and decision events.
            "events": combined_events,

            "prediction": prediction_dict,

            "recommendation":
                recommendation_dict,

            "recommendation_actions":
                actions,

            "recovery_summary": {
                # Existing aliases retained for the
                # current frontend implementation.
                "predicted_turn_time_minutes":
                    predicted_turn_time,

                "total_minutes_saved":
                    proposed_minutes_saved,

                "projected_turn_time_minutes":
                    proposed_projected_turn_time,

                "sla_recovered":
                    proposed_sla_recovered,

                # Full AI-proposed plan.
                "proposed_minutes_saved":
                    proposed_minutes_saved,

                "proposed_projected_turn_time_minutes":
                    proposed_projected_turn_time,

                "proposed_sla_recovered":
                    proposed_sla_recovered,

                # Warehouse-accepted plan.
                "accepted_minutes_saved":
                    accepted_minutes_saved,

                "accepted_projected_turn_time_minutes":
                    accepted_projected_turn_time,

                "accepted_sla_recovered":
                    accepted_sla_recovered,

                "accepted_action_cost":
                    accepted_action_cost,

                # Remaining decision impact.
                "rejected_minutes_saved":
                    rejected_minutes_saved,

                "pending_minutes_saved":
                    pending_minutes_saved,

                # Canonical completed-outcome view used by
                # the chart, table and appointment drawer.
                "completed_outcome": completed_outcome,
                "is_completed": is_completed,
                "was_late": was_late,
                "actual_sla_met": actual_sla_met,
                "actual_sla_missed": actual_sla_missed,
                "recommendation_used": recommendation_used,
                "accepted_action_count": len(accepted_actions),
                "actual_turn_time_minutes": actual_turn_time,
                "sla_variance_minutes": sla_variance_minutes,
                "sla_outcome_status": sla_outcome_status,
                "sla_outcome_reason": sla_outcome_reason,
                "risk_contributors": risk_contributors,

                "sla_minutes":
                    sla_minutes,
            },
        }

    def get_reference_data(self) -> dict[str, list[dict[str, str | None]]]:
        facilities = self.db.execute(text("""
            SELECT facility_id AS id, facility_name AS label, NULL::VARCHAR AS facility_id
            FROM facilities WHERE active = TRUE ORDER BY facility_name;
        """)).mappings().all()
        customers = self.db.execute(text("""
            SELECT customer_id AS id, customer_name AS label, NULL::VARCHAR AS facility_id
            FROM customers ORDER BY customer_name;
        """)).mappings().all()
        carriers = self.db.execute(text("""
            SELECT carrier_id AS id, carrier_name AS label, NULL::VARCHAR AS facility_id
            FROM carriers WHERE active = TRUE ORDER BY carrier_name;
        """)).mappings().all()
        docks = self.db.execute(text("""
            SELECT dock_id AS id, dock_name AS label, facility_id
            FROM docks WHERE active = TRUE ORDER BY facility_id, dock_name;
        """)).mappings().all()
        products = self.db.execute(text("""
            SELECT
                product_id AS id,
                CONCAT(product_name, ' · ', sku) AS label,
                sku,
                category,
                unit_of_measure,
                unit_weight_lb,
                unit_volume_cuft,
                units_per_case,
                cases_per_pallet
            FROM products
            WHERE active = TRUE
            ORDER BY product_name, sku;
        """)).mappings().all()
        return {
            "facilities": [dict(row) for row in facilities],
            "customers": [dict(row) for row in customers],
            "carriers": [dict(row) for row in carriers],
            "docks": [dict(row) for row in docks],
            "products": [dict(row) for row in products],
        }

    def get_filter_reference_data(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, list[dict[str, str | None]]]:
        """Return cascading dashboard filter choices.

        Each option list applies every active filter except its own dimension,
        so a selected value in one slicer immediately removes values from the
        other slicers that have no matching appointments.
        """

        def build_conditions(exclude: str) -> tuple[str, dict[str, object]]:
            conditions = ["a.appt_id LIKE 'DEMO%'"]
            params: dict[str, object] = {}

            if exclude != "facility" and facility_id:
                conditions.append("a.facility_id = :facility_id")
                params["facility_id"] = facility_id
            if exclude != "customer" and customer_id:
                conditions.append("a.customer_id = :customer_id")
                params["customer_id"] = customer_id
            if exclude != "carrier" and carrier_id:
                conditions.append("a.carrier_id = :carrier_id")
                params["carrier_id"] = carrier_id
            if exclude != "appointment_type" and appointment_type:
                conditions.append("LOWER(a.appointment_type) = LOWER(:appointment_type)")
                params["appointment_type"] = appointment_type
            if date_from:
                conditions.append("a.scheduled_time >= :date_from")
                params["date_from"] = date_from
            if date_to:
                conditions.append("a.scheduled_time < :date_to")
                params["date_to"] = date_to

            return " AND ".join(conditions), params

        facility_where, facility_params = build_conditions("facility")
        customer_where, customer_params = build_conditions("customer")
        carrier_where, carrier_params = build_conditions("carrier")
        type_where, type_params = build_conditions("appointment_type")

        facilities = self.db.execute(
            text(f"""
                SELECT DISTINCT
                    a.facility_id AS id,
                    f.facility_name AS label,
                    NULL::VARCHAR AS facility_id
                FROM appointments a
                JOIN facilities f ON f.facility_id = a.facility_id
                WHERE {facility_where}
                  AND f.active = TRUE
                ORDER BY label;
            """),
            facility_params,
        ).mappings().all()

        customers = self.db.execute(
            text(f"""
                SELECT DISTINCT
                    a.customer_id AS id,
                    COALESCE(c.customer_name, a.customer_name, a.customer_id) AS label,
                    NULL::VARCHAR AS facility_id
                FROM appointments a
                LEFT JOIN customers c ON c.customer_id = a.customer_id
                WHERE {customer_where}
                  AND a.customer_id IS NOT NULL
                ORDER BY label;
            """),
            customer_params,
        ).mappings().all()

        carriers = self.db.execute(
            text(f"""
                SELECT DISTINCT
                    a.carrier_id AS id,
                    COALESCE(c.carrier_name, a.carrier_id) AS label,
                    NULL::VARCHAR AS facility_id
                FROM appointments a
                LEFT JOIN carriers c ON c.carrier_id = a.carrier_id
                WHERE {carrier_where}
                  AND a.carrier_id IS NOT NULL
                ORDER BY label;
            """),
            carrier_params,
        ).mappings().all()

        appointment_types = self.db.execute(
            text(f"""
                SELECT DISTINCT
                    a.appointment_type AS id,
                    a.appointment_type AS label,
                    NULL::VARCHAR AS facility_id
                FROM appointments a
                WHERE {type_where}
                  AND a.appointment_type IN ('Inbound', 'Outbound')
                ORDER BY label;
            """),
            type_params,
        ).mappings().all()

        return {
            "facilities": [dict(row) for row in facilities],
            "customers": [dict(row) for row in customers],
            "carriers": [dict(row) for row in carriers],
            "appointment_types": [dict(row) for row in appointment_types],
        }

    def generate_next_demo_id(self) -> str:
        value = self.db.execute(text("""
            SELECT COALESCE(MAX(CAST(SUBSTRING(appt_id FROM 5) AS INTEGER)), 0) + 1
            FROM appointments
            WHERE appt_id ~ '^DEMO[0-9]+$';
        """)).scalar_one()
        return f"DEMO{int(value):07d}"

    def validate_references(
        self,
        *,
        facility_id: str,
        customer_id: str | None,
        carrier_id: str | None,
        dock_id: str | None,
    ) -> dict[str, str | None]:
        facility = self.db.execute(text("SELECT facility_name FROM facilities WHERE facility_id=:id AND active=TRUE"), {"id": facility_id}).scalar_one_or_none()
        if facility is None:
            raise ValueError("Selected facility is unavailable.")
        customer = None
        if customer_id:
            customer = self.db.execute(text("SELECT customer_name FROM customers WHERE customer_id=:id"), {"id": customer_id}).scalar_one_or_none()
            if customer is None:
                raise ValueError("Selected customer was not found.")
        carrier = None
        if carrier_id:
            carrier = self.db.execute(text("SELECT carrier_name FROM carriers WHERE carrier_id=:id AND active=TRUE"), {"id": carrier_id}).scalar_one_or_none()
            if carrier is None:
                raise ValueError("Selected carrier is unavailable.")
        if dock_id:
            dock_facility = self.db.execute(text("SELECT facility_id FROM docks WHERE dock_id=:id AND active=TRUE"), {"id": dock_id}).scalar_one_or_none()
            if dock_facility is None:
                raise ValueError("Selected dock is unavailable.")
            if dock_facility != facility_id:
                raise ValueError("Selected dock does not belong to the selected facility.")
        return {"facility_name": facility, "customer_name": customer, "carrier_name": carrier}

    def validate_products(
        self,
        products: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not products:
            return []

        product_ids = [item["product_id"] for item in products]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product can only be added once per appointment.")

        rows = self.db.execute(
            text(
                """
                SELECT
                    product_id, product_name, sku, unit_of_measure,
                    unit_weight_lb, unit_volume_cuft,
                    units_per_case, cases_per_pallet
                FROM products
                WHERE active = TRUE
                  AND product_id = ANY(:product_ids);
                """
            ),
            {"product_ids": product_ids},
        ).mappings().all()

        by_id = {row["product_id"]: dict(row) for row in rows}
        missing = [product_id for product_id in product_ids if product_id not in by_id]
        if missing:
            raise ValueError(f"One or more selected products are unavailable: {', '.join(missing)}")

        validated: list[dict[str, Any]] = []
        for item in products:
            product = by_id[item["product_id"]]
            quantity = int(item["quantity"] or 0)
            if quantity < 1:
                raise ValueError("Product quantity must be at least 1.")

            units_per_case = max(1, int(product["units_per_case"] or 1))
            cases_per_pallet = max(1, int(product["cases_per_pallet"] or 1))
            case_count = (quantity + units_per_case - 1) // units_per_case
            pallet_count = (case_count + cases_per_pallet - 1) // cases_per_pallet

            validated.append({
                **product,
                "quantity": quantity,
                "case_count": case_count,
                "pallet_count": pallet_count,
                "line_weight_lb": round(float(product["unit_weight_lb"]) * quantity, 2),
                "line_volume_cuft": round(float(product["unit_volume_cuft"]) * quantity, 4),
            })

        return validated

    def create_appointment_products(
        self,
        *,
        appt_id: str,
        products: list[dict[str, Any]],
    ) -> None:
        for product in products:
            self.db.execute(
                text(
                    """
                    INSERT INTO appointment_products (
                        appt_id, product_id, quantity, case_count,
                        pallet_count, line_weight_lb, line_volume_cuft
                    ) VALUES (
                        :appt_id, :product_id, :quantity, :case_count,
                        :pallet_count, :line_weight_lb, :line_volume_cuft
                    );
                    """
                ),
                {"appt_id": appt_id, **product},
            )
        self.db.commit()

    def create_initial_event(self, appt_id: str, event_time: datetime) -> None:
        self.create_audit_event(
            appt_id=appt_id,
            event_type="APPOINTMENT_CREATED",
            event_time=event_time,
            notes="Appointment created in Control Tower portal",
            performed_by="Operations Planner",
            details={"source": "control_tower"},
        )

    def create_audit_event(
        self,
        *,
        appt_id: str,
        event_type: str,
        event_time: datetime,
        notes: str | None = None,
        performed_by: str | None = None,
        field_name: str | None = None,
        old_value: Any | None = None,
        new_value: Any | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        import json

        def serialize(value: Any | None) -> str | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        self.db.execute(
            text(
                """
                INSERT INTO appointment_events (
                    appt_id,
                    event_type,
                    event_time,
                    notes,
                    performed_by,
                    field_name,
                    old_value,
                    new_value,
                    details_json
                ) VALUES (
                    :appt_id,
                    :event_type,
                    :event_time,
                    :notes,
                    :performed_by,
                    :field_name,
                    :old_value,
                    :new_value,
                    CAST(:details_json AS JSONB)
                );
                """
            ),
            {
                "appt_id": appt_id,
                "event_type": event_type,
                "event_time": event_time,
                "notes": notes,
                "performed_by": performed_by,
                "field_name": field_name,
                "old_value": serialize(old_value),
                "new_value": serialize(new_value),
                "details_json": json.dumps(
                    details or {},
                    default=str,
                ),
            },
        )
        self.db.commit()

    def get_scoring_row(self, appt_id: str) -> dict[str, Any] | None:
        row = self.db.execute(text("""
            SELECT a.appt_id, a.scheduled_time, a.estimated_arrival_time, a.facility_id,
                   a.carrier_id, a.customer_id, a.assigned_dock_id, a.appointment_type,
                   a.load_type, a.pallet_count, a.sku_count, a.total_weight, a.total_cube,
                   a.priority, a.sla_minutes, a.detention_cost_per_hour, a.distance_band,
                   a.traffic_severity, a.weather_severity, a.surge_indicator
            FROM appointments a WHERE a.appt_id=:appt_id;
        """), {"appt_id": appt_id}).mappings().one_or_none()
        return dict(row) if row else None

    def save_prediction(self, prediction: dict[str, Any]) -> None:
        self.db.execute(text("""
            INSERT INTO appointment_predictions (
                appt_id, predicted_arrival_time, predicted_delay_minutes,
                predicted_duration_minutes, sla_miss_probability,
                sla_recovery_probability, turn_risk_score, predicted_missed,
                model_version, generated_at
            ) VALUES (
                :appt_id, :predicted_arrival_time, :predicted_delay_minutes,
                :predicted_duration_minutes, :sla_miss_probability,
                :sla_recovery_probability, :turn_risk_score, :predicted_missed,
                :model_version, NOW()
            );
        """), prediction)
        self.db.commit()

    def create_initial_recommendation(
        self,
        *,
        appt_id: str,
        dock_id: str | None,
        predicted_duration_minutes: int,
        sla_minutes: int,
        detention_cost_per_hour: float,
    ) -> int:
        minutes_over = max(0, predicted_duration_minutes - sla_minutes)
        estimated_loss = round((minutes_over / 60) * detention_cost_per_hour, 2)
        action_cost = 75.0
        estimated_savings = max(0.0, round(estimated_loss - action_cost, 2))
        recommendation_id = self.db.execute(text("""
            INSERT INTO appointment_recommendations (
                appt_id, recommendation_type, recommended_action,
                recommended_dock_id, recommended_sequence, additional_labor,
                estimated_loss_without_action, estimated_cost_of_action,
                estimated_savings, status, created_at
            ) VALUES (
                :appt_id, 'SLA Recovery',
                'Add one loader, pre-stage products and protect the assigned dock window',
                :dock_id, 1, 1, :estimated_loss, :action_cost,
                :estimated_savings, 'Pending', NOW()
            ) RETURNING recommendation_id;
        """), {
            "appt_id": appt_id,
            "dock_id": dock_id,
            "estimated_loss": estimated_loss,
            "action_cost": action_cost,
            "estimated_savings": estimated_savings,
        }).scalar_one()
        actions = [
            {
                "sequence_number": 1,
                "action_code": "ADD_LOADER",
                "action_title": "Assign one additional loader",
                "action_description": "Add temporary labor capacity to reduce handling time.",
                "owner_role": "Warehouse Supervisor",
                "estimated_minutes_saved": min(20, max(8, minutes_over // 3 or 8)),
                "additional_loaders": 1,
                "additional_forklifts": 0,
                "required_dock_id": None,
                "estimated_action_cost": 40.0,
            },
            {
                "sequence_number": 2,
                "action_code": "PRE_STAGE_PRODUCTS",
                "action_title": "Pre-stage appointment products",
                "action_description": "Stage high-volume products before the trailer reaches the dock.",
                "owner_role": "Inventory Coordinator",
                "estimated_minutes_saved": min(18, max(6, minutes_over // 4 or 6)),
                "additional_loaders": 0,
                "additional_forklifts": 0,
                "required_dock_id": None,
                "estimated_action_cost": 20.0,
            },
            {
                "sequence_number": 3,
                "action_code": "RESERVE_DOCK",
                "action_title": "Reserve the assigned dock",
                "action_description": "Protect the dock window from conflicting appointment moves.",
                "owner_role": "Dock Coordinator",
                "estimated_minutes_saved": min(15, max(5, minutes_over // 5 or 5)),
                "additional_loaders": 0,
                "additional_forklifts": 0,
                "required_dock_id": dock_id,
                "estimated_action_cost": 15.0,
            },
        ]
        for action in actions:
            self.db.execute(text("""
                INSERT INTO recommendation_actions (
                    recommendation_id, sequence_number, action_code,
                    action_title, action_description, owner_role,
                    estimated_minutes_saved, additional_loaders,
                    additional_forklifts, required_dock_id,
                    estimated_action_cost, status, created_at
                ) VALUES (
                    :recommendation_id, :sequence_number, :action_code,
                    :action_title, :action_description, :owner_role,
                    :estimated_minutes_saved, :additional_loaders,
                    :additional_forklifts, :required_dock_id,
                    :estimated_action_cost, 'Proposed', NOW()
                );
            """), {"recommendation_id": recommendation_id, **action})
        self.db.commit()
        return int(recommendation_id)

    def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Appointment]:
        statement = (
            select(Appointment)
            .order_by(
                Appointment.scheduled_time
            )
            .limit(limit)
            .offset(offset)
        )

        return list(
            self.db.scalars(
                statement
            ).all()
        )

    def count_all(self) -> int:
        statement = select(
            func.count(
                Appointment.appt_id
            )
        )

        return int(
            self.db.scalar(statement)
            or 0
        )

    def get_by_id(
        self,
        appt_id: str,
    ) -> Appointment | None:
        return self.db.get(
            Appointment,
            appt_id,
        )


    def update_appointment(
        self,
        *,
        appt_id: str,
        values: dict[str, Any],
    ) -> Appointment:
        appointment = self.get_by_id(appt_id)
        if appointment is None:
            raise ValueError("Appointment not found.")
        for key, value in values.items():
            setattr(appointment, key, value)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def reschedule_appointment(
        self,
        *,
        appt_id: str,
        scheduled_time: datetime,
        changed_at: datetime,
    ) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                UPDATE appointments
                SET
                    original_scheduled_time = COALESCE(original_scheduled_time, scheduled_time),
                    estimated_arrival_time =
                        CASE
                            WHEN estimated_arrival_time IS NULL THEN NULL
                            ELSE estimated_arrival_time + (CAST(:scheduled_time AS TIMESTAMP) - scheduled_time)
                        END,
                    scheduled_time = CAST(:scheduled_time AS TIMESTAMP),
                    appt_date = CAST(:scheduled_time AS TIMESTAMP),
                    is_rescheduled = TRUE,
                    reschedule_count = COALESCE(reschedule_count, 0) + 1,
                    rescheduled_at = CAST(:changed_at AS TIMESTAMP),
                    status = 'Scheduled',
                    updated_at = CAST(:changed_at AS TIMESTAMP)
                WHERE appt_id = :appt_id
                RETURNING
                    appt_id,
                    original_scheduled_time,
                    scheduled_time,
                    estimated_arrival_time,
                    is_rescheduled,
                    reschedule_count,
                    rescheduled_at;
                """
            ),
            {
                "appt_id": appt_id,
                "scheduled_time": scheduled_time,
                "changed_at": changed_at,
            },
        ).mappings().one()
        self.db.commit()
        return dict(row)

    def replace_appointment_products(
        self,
        *,
        appt_id: str,
        products: list[dict[str, Any]],
    ) -> None:
        self.db.execute(
            text("DELETE FROM appointment_products WHERE appt_id = :appt_id"),
            {"appt_id": appt_id},
        )
        for product in products:
            self.db.execute(
                text(
                    """
                    INSERT INTO appointment_products (
                        appt_id, product_id, quantity, case_count,
                        pallet_count, line_weight_lb, line_volume_cuft
                    ) VALUES (
                        :appt_id, :product_id, :quantity, :case_count,
                        :pallet_count, :line_weight_lb, :line_volume_cuft
                    )
                    """
                ),
                {"appt_id": appt_id, **product},
            )
        self.db.commit()

    def create_update_event(
        self,
        *,
        appt_id: str,
        event_time: datetime,
        notes: str,
        performed_by: str = "Operations Planner",
    ) -> None:
        self.create_audit_event(
            appt_id=appt_id,
            event_type="APPOINTMENT_UPDATED",
            event_time=event_time,
            notes=notes,
            performed_by=performed_by,
        )

    def supersede_pending_recommendations(self, appt_id: str) -> None:
        self.db.execute(
            text(
                """
                UPDATE appointment_recommendations
                SET status = 'Superseded'
                WHERE appt_id = :appt_id
                  AND status = 'Pending'
                """
            ),
            {"appt_id": appt_id},
        )
        self.db.commit()

    def create(
        self,
        appointment: Appointment,
    ) -> Appointment:
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)

        return appointment

    def rollback(self) -> None:
        self.db.rollback()