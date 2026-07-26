from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import Appointment


class AppointmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        facility_id: str | None = None,
        status: str | None = None,
        risk_level: str | None = None,
        outcome: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size

        parameters = {
            "page_size": page_size,
            "offset": offset,
            "facility_id": facility_id,
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
                      OR a.facility_id = :facility_id
                  )

                  AND (
                      CAST(:status AS VARCHAR) IS NULL
                      OR a.status = :status
                  )

                  AND (
                      CAST(:search AS VARCHAR) IS NULL
                      OR a.appt_id ILIKE :search
                      OR a.customer_name ILIKE :search
                      OR c.carrier_name ILIKE :search
                  )

                  AND (
                      CAST(:risk_level AS VARCHAR) IS NULL

                      OR (
                          :risk_level = 'Low'
                          AND p.turn_risk_score < 30
                      )

                      OR (
                          :risk_level = 'Medium'
                          AND p.turn_risk_score >= 30
                          AND p.turn_risk_score < 60
                      )

                      OR (
                          :risk_level = 'High'
                          AND p.turn_risk_score >= 60
                          AND p.turn_risk_score < 80
                      )

                      OR (
                          :risk_level = 'Critical'
                          AND p.turn_risk_score >= 80
                      )
                  )

                  AND (
                      CAST(:outcome AS VARCHAR) IS NULL

                      OR (
                          :outcome =
                              'Recovered with recommendations'
                          AND a.status = 'Completed'
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_sla_missed = FALSE
                          AND EXISTS (
    SELECT 1

    FROM appointment_recommendations outcome_r

    WHERE outcome_r.appt_id = a.appt_id

      AND (
          outcome_r.status = 'Completed'

          OR EXISTS (
              SELECT 1
              FROM recommendation_actions
                  outcome_action
              WHERE
                  outcome_action.recommendation_id =
                      outcome_r.recommendation_id
                  AND outcome_action.decision_status =
                      'Accepted'
          )
      )
)
                      )

                      OR (
                          :outcome =
                              'Recovered without recommendations'
                          AND a.status = 'Completed'
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_sla_missed = FALSE
                          AND NOT EXISTS (
    SELECT 1

    FROM appointment_recommendations outcome_r

    WHERE outcome_r.appt_id = a.appt_id

      AND (
          outcome_r.status = 'Completed'

          OR EXISTS (
              SELECT 1
              FROM recommendation_actions
                  outcome_action
              WHERE
                  outcome_action.recommendation_id =
                      outcome_r.recommendation_id
                  AND outcome_action.decision_status =
                      'Accepted'
          )
      )
)
                      )

                      OR (
                          :outcome = 'Missed SLA'
                          AND a.status = 'Completed'
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_sla_missed = TRUE
                      )
                  )

                ORDER BY
                    p.turn_risk_score DESC NULLS LAST,
                    a.scheduled_time ASC

                LIMIT :page_size
                OFFSET :offset;
                """
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
                      OR a.facility_id = :facility_id
                  )

                  AND (
                      CAST(:status AS VARCHAR) IS NULL
                      OR a.status = :status
                  )

                  AND (
                      CAST(:search AS VARCHAR) IS NULL
                      OR a.appt_id ILIKE :search
                      OR a.customer_name ILIKE :search
                      OR c.carrier_name ILIKE :search
                  )

                  AND (
                      CAST(:risk_level AS VARCHAR) IS NULL

                      OR (
                          :risk_level = 'Low'
                          AND p.turn_risk_score < 30
                      )

                      OR (
                          :risk_level = 'Medium'
                          AND p.turn_risk_score >= 30
                          AND p.turn_risk_score < 60
                      )

                      OR (
                          :risk_level = 'High'
                          AND p.turn_risk_score >= 60
                          AND p.turn_risk_score < 80
                      )

                      OR (
                          :risk_level = 'Critical'
                          AND p.turn_risk_score >= 80
                      )
                  )

                  AND (
                      CAST(:outcome AS VARCHAR) IS NULL

                      OR (
                          :outcome =
                              'Recovered with recommendations'
                          AND a.status = 'Completed'
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_sla_missed = FALSE
                          AND EXISTS (
    SELECT 1

    FROM appointment_recommendations outcome_r

    WHERE outcome_r.appt_id = a.appt_id

      AND (
          outcome_r.status = 'Completed'

          OR EXISTS (
              SELECT 1
              FROM recommendation_actions
                  outcome_action
              WHERE
                  outcome_action.recommendation_id =
                      outcome_r.recommendation_id
                  AND outcome_action.decision_status =
                      'Accepted'
          )
      )
)
                      )

                      OR (
                          :outcome =
                              'Recovered without recommendations'
                          AND a.status = 'Completed'
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_sla_missed = FALSE
                          AND NOT EXISTS (
    SELECT 1

    FROM appointment_recommendations outcome_r

    WHERE outcome_r.appt_id = a.appt_id

      AND (
          outcome_r.status = 'Completed'

          OR EXISTS (
              SELECT 1
              FROM recommendation_actions
                  outcome_action
              WHERE
                  outcome_action.recommendation_id =
                      outcome_r.recommendation_id
                  AND outcome_action.decision_status =
                      'Accepted'
          )
      )
)
                      )

                      OR (
                          :outcome = 'Missed SLA'
                          AND a.status = 'Completed'
                          AND a.actual_arrival_delay_minutes > 0
                          AND a.actual_sla_missed = TRUE
                      )
                  );
                """
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
                    a.appointment_type,
                    a.load_type,
                    a.trailer_number,

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
                    notes

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
                    ) AS notes

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

            actions = [
                dict(row)
                for row in action_rows
            ]

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

                "sla_minutes":
                    sla_minutes,
            },
        }

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