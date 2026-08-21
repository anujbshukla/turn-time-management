from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


OPTIMIZER_VERSION = "multi-appointment-v3.0-outcome-learning"


@dataclass(frozen=True)
class InterventionOption:
    action_codes: tuple[str, ...]
    minutes_saved: int
    extra_loaders: int = 0
    extra_forklifts: int = 0
    staging_labor: int = 0
    action_cost: float = 0.0


OPTIONS: tuple[InterventionOption, ...] = (
    InterventionOption((), 0, action_cost=0.0),
    InterventionOption(("ADD_FORKLIFT",), 9, extra_forklifts=1, action_cost=35.0),
    InterventionOption(("ADD_LOADER",), 12, extra_loaders=1, action_cost=50.0),
    InterventionOption(("PRE_STAGE_PRODUCTS",), 15, staging_labor=1, action_cost=20.0),
    InterventionOption(
        ("ADD_LOADER", "ADD_FORKLIFT"),
        21,
        extra_loaders=1,
        extra_forklifts=1,
        action_cost=85.0,
    ),
    InterventionOption(
        ("ADD_FORKLIFT", "PRE_STAGE_PRODUCTS"),
        24,
        extra_forklifts=1,
        staging_labor=1,
        action_cost=55.0,
    ),
    InterventionOption(
        ("ADD_LOADER", "PRE_STAGE_PRODUCTS"),
        27,
        extra_loaders=1,
        staging_labor=1,
        action_cost=70.0,
    ),
    InterventionOption(
        ("ADD_LOADER", "ADD_FORKLIFT", "PRE_STAGE_PRODUCTS"),
        36,
        extra_loaders=1,
        extra_forklifts=1,
        staging_labor=1,
        action_cost=105.0,
    ),
)


class MultiAppointmentOptimizerService:
    """Coordinate recovery across all at-risk appointments in one window.

    ML-v2 provides the predictive layer. It already captures product handling
    history, pallets/SKUs, carrier/customer/facility behavior, congestion and
    planned resources. This service is the prescriptive layer: it allocates
    constrained labor/equipment across appointments jointly and prevents two
    recommendations from consuming the same hourly resource headroom.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _pallet_band(value: Any) -> str:
        pallets = int(value or 0)
        if pallets < 10:
            return "<10"
        if pallets < 20:
            return "10-19"
        if pallets < 30:
            return "20-29"
        if pallets < 40:
            return "30-39"
        return "40+"

    @staticmethod
    def _congestion_band(value: Any) -> str:
        congestion = float(value or 0)
        if congestion < 25:
            return "Low"
        if congestion < 50:
            return "Moderate"
        if congestion < 75:
            return "High"
        return "Severe"

    @staticmethod
    def _action_signature(
        action_codes: tuple[str, ...] | list[str],
    ) -> str:
        return "+".join(sorted(set(action_codes)))

    def _load_action_effectiveness(
        self,
        facility_id: str,
    ) -> dict[tuple[str, str, str, str, str, str], dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    action_signature,
                    appointment_type,
                    load_type,
                    temperature_zone,
                    pallet_band,
                    congestion_band,
                    sample_size,
                    sla_success_rate,
                    avg_realized_minutes_saved,
                    avg_realized_net_savings,
                    confidence_weight
                FROM optimization_action_effectiveness
                WHERE facility_id = :facility_id;
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        return {
            (
                str(row["action_signature"]),
                str(row["appointment_type"]),
                str(row["load_type"]),
                str(row["temperature_zone"]),
                str(row["pallet_band"]),
                str(row["congestion_band"]),
            ): dict(row)
            for row in rows
        }

    @classmethod
    def _learned_option_estimate(
        cls,
        row: dict[str, Any],
        option: InterventionOption,
        profiles: dict[
            tuple[str, str, str, str, str, str],
            dict[str, Any],
        ] | None,
    ) -> dict[str, Any]:
        baseline_minutes = float(option.minutes_saved)
        if not option.action_codes or not profiles:
            return {
                "minutes_saved": baseline_minutes,
                "sample_size": 0,
                "confidence_weight": 0.0,
                "sla_success_rate": None,
                "avg_realized_net_savings": None,
                "source": "baseline_assumption",
            }

        key = (
            cls._action_signature(option.action_codes),
            str(row.get("appointment_type") or "Unknown"),
            str(row.get("load_type") or "Unknown"),
            str(row.get("required_temperature_zone") or "Ambient"),
            cls._pallet_band(row.get("pallet_count")),
            cls._congestion_band(
                row.get("dock_congestion_percent")
            ),
        )
        profile = profiles.get(key)
        if not profile:
            return {
                "minutes_saved": baseline_minutes,
                "sample_size": 0,
                "confidence_weight": 0.0,
                "sla_success_rate": None,
                "avg_realized_net_savings": None,
                "source": "baseline_assumption",
            }

        sample_size = int(profile.get("sample_size") or 0)
        confidence = max(
            0.0,
            min(
                0.85,
                float(profile.get("confidence_weight") or 0),
            ),
        )
        # Require at least three realized appointments before learned
        # effectiveness can change the intervention estimate.
        if sample_size < 3:
            confidence = 0.0

        learned_minutes = max(
            0.0,
            float(
                profile.get("avg_realized_minutes_saved")
                or 0
            ),
        )
        blended_minutes = (
            baseline_minutes * (1.0 - confidence)
            + learned_minutes * confidence
        )

        # Keep learned effects within an operationally defensible range.
        blended_minutes = max(
            0.0,
            min(
                baseline_minutes * 1.75,
                blended_minutes,
            ),
        )

        return {
            "minutes_saved": round(blended_minutes, 2),
            "sample_size": sample_size,
            "confidence_weight": round(confidence, 4),
            "sla_success_rate": (
                float(profile["sla_success_rate"])
                if profile.get("sla_success_rate") is not None
                else None
            ),
            "avg_realized_net_savings": (
                float(profile["avg_realized_net_savings"])
                if profile.get("avg_realized_net_savings") is not None
                else None
            ),
            "source": (
                "realized_outcome_learning"
                if confidence > 0
                else "baseline_assumption"
            ),
        }

    def preview(
        self,
        *,
        facility_id: str | None = None,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        date_from: date | datetime | None = None,
        date_to: date | datetime | None = None,
        max_missions: int = 5,
        max_extra_loaders_per_hour: int | None = None,
        max_extra_forklifts_per_hour: int | None = None,
        max_staging_labor_per_hour: int | None = None,
        allow_dock_reassignment: bool = True,
    ) -> dict[str, Any]:
        window_start, window_end = self._resolve_window(
            date_from,
            date_to,
        )
        candidates = self._load_candidates(
            facility_id=facility_id,
            customer_id=customer_id,
            carrier_id=carrier_id,
            appointment_type=appointment_type,
            window_start=window_start,
            window_end=window_end,
        )

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in candidates:
            grouped[str(row["facility_id"])].append(row)

        missions: list[dict[str, Any]] = []
        for current_facility_id, rows in grouped.items():
            mission = self._optimize_facility(
                current_facility_id,
                rows,
                window_start,
                window_end,
                max_extra_loaders_per_hour=
                    max_extra_loaders_per_hour,
                max_extra_forklifts_per_hour=
                    max_extra_forklifts_per_hour,
                max_staging_labor_per_hour=
                    max_staging_labor_per_hour,
                allow_dock_reassignment=
                    allow_dock_reassignment,
            )
            if mission is not None:
                missions.append(mission)

        missions.sort(
            key=lambda mission: (
                -int(mission["projected_sla_misses_before"]),
                -int(mission["priority_score"]),
                -float(mission["estimated_financial_benefit"]),
            )
        )

        missions = missions[:max_missions]
        return {
            "optimizer_version": OPTIMIZER_VERSION,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "candidate_appointments": len(candidates),
            "facility_count": len(grouped),
            "scenario_constraints": {
                "max_extra_loaders_per_hour":
                    max_extra_loaders_per_hour,
                "max_extra_forklifts_per_hour":
                    max_extra_forklifts_per_hour,
                "max_staging_labor_per_hour":
                    max_staging_labor_per_hour,
                "allow_dock_reassignment":
                    allow_dock_reassignment,
            },
            "missions": missions,
        }

    def run_and_persist(self, **kwargs: Any) -> dict[str, Any]:
        preview = self.preview(**kwargs)
        persisted: list[dict[str, Any]] = []

        for mission in preview["missions"]:
            mission_id = self.db.execute(
                text(
                    """
                    INSERT INTO optimization_missions (
                        facility_id,
                        window_start,
                        window_end,
                        status,
                        appointments_at_risk,
                        projected_sla_misses_before,
                        projected_sla_misses_after,
                        estimated_net_savings,
                        optimizer_version,
                        created_at
                    ) VALUES (
                        :facility_id,
                        :window_start,
                        :window_end,
                        'Proposed',
                        :appointments_at_risk,
                        :projected_sla_misses_before,
                        :projected_sla_misses_after,
                        :estimated_net_savings,
                        :optimizer_version,
                        NOW()
                    )
                    RETURNING mission_id;
                    """
                ),
                {
                    "facility_id": mission["facility_id"],
                    "window_start": mission["window_start"],
                    "window_end": mission["window_end"],
                    "appointments_at_risk": mission["appointments_at_risk"],
                    "projected_sla_misses_before": mission[
                        "projected_sla_misses_before"
                    ],
                    "projected_sla_misses_after": mission[
                        "projected_sla_misses_after"
                    ],
                    "estimated_net_savings": mission[
                        "estimated_financial_benefit"
                    ],
                    "optimizer_version": OPTIMIZER_VERSION,
                },
            ).scalar_one()

            for item in mission["appointment_plan"]:
                self.db.execute(
                    text(
                        """
                        INSERT INTO optimization_mission_appointments (
                            mission_id,
                            appt_id,
                            baseline_risk_score,
                            baseline_projected_turn_minutes,
                            optimized_projected_turn_minutes,
                            sla_recovered,
                            priority_order
                        ) VALUES (
                            :mission_id,
                            :appt_id,
                            :baseline_risk_score,
                            :baseline_projected_turn_minutes,
                            :optimized_projected_turn_minutes,
                            :sla_recovered,
                            :priority_order
                        );
                        """
                    ),
                    {
                        "mission_id": mission_id,
                        "appt_id": item["appt_id"],
                        "baseline_risk_score": item["baseline_risk_score"],
                        "baseline_projected_turn_minutes": item[
                            "baseline_projected_turn_minutes"
                        ],
                        "optimized_projected_turn_minutes": item[
                            "optimized_projected_turn_minutes"
                        ],
                        "sla_recovered": item["sla_recovered"],
                        "priority_order": item["priority_order"],
                    },
                )

                for sequence_number, action in enumerate(item["actions"], start=1):
                    self.db.execute(
                        text(
                            """
                            INSERT INTO optimization_mission_actions (
                                mission_id,
                                appt_id,
                                sequence_number,
                                action_code,
                                action_description,
                                additional_loaders,
                                additional_forklifts,
                                staging_labor,
                                required_dock_id,
                                expected_minutes_saved,
                                estimated_action_cost,
                                status,
                                created_at
                            ) VALUES (
                                :mission_id,
                                :appt_id,
                                :sequence_number,
                                :action_code,
                                :action_description,
                                :additional_loaders,
                                :additional_forklifts,
                                :staging_labor,
                                :required_dock_id,
                                :expected_minutes_saved,
                                :estimated_action_cost,
                                'Proposed',
                                NOW()
                            );
                            """
                        ),
                        {
                            "mission_id": mission_id,
                            "appt_id": item["appt_id"],
                            "sequence_number": sequence_number,
                            **action,
                        },
                    )

            persisted.append(
                {
                    **mission,
                    "database_mission_id": int(mission_id),
                    "mission_id": f"optimizer-{mission_id}",
                }
            )

        self.db.commit()
        return {
            **preview,
            "missions": persisted,
            "persisted": True,
        }

    def accept_preview(
        self,
        *,
        facility_id: str,
        window_start: datetime,
        window_end: datetime,
        customer_id: str | None = None,
        carrier_id: str | None = None,
        appointment_type: str | None = None,
        max_extra_loaders_per_hour: int | None = None,
        max_extra_forklifts_per_hour: int | None = None,
        max_staging_labor_per_hour: int | None = None,
        allow_dock_reassignment: bool = True,
    ) -> dict[str, Any]:
        """Re-optimize the exact mission window, persist it and accept it.

        Acceptance is intentionally server-side. The coordinated plan is
        revalidated against current resource headroom immediately before it is
        committed, preventing a stale browser preview from reserving resources.
        """
        result = self.run_and_persist(
            facility_id=facility_id,
            customer_id=customer_id,
            carrier_id=carrier_id,
            appointment_type=appointment_type,
            date_from=window_start,
            date_to=window_end,
            max_missions=1,
            max_extra_loaders_per_hour=
                max_extra_loaders_per_hour,
            max_extra_forklifts_per_hour=
                max_extra_forklifts_per_hour,
            max_staging_labor_per_hour=
                max_staging_labor_per_hour,
            allow_dock_reassignment=
                allow_dock_reassignment,
        )
        missions = result.get("missions", [])
        if not missions:
            raise ValueError(
                "No feasible coordinated recovery mission exists for the selected operating window."
            )

        mission = missions[0]
        mission_id = int(mission["database_mission_id"])
        execution = self.update_status(
            mission_id,
            "Accepted",
        )
        return {
            **mission,
            **execution,
            "database_mission_id": mission_id,
            "mission_id": f"optimizer-{mission_id}",
        }

    def latest(
        self,
        *,
        facility_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        conditions = ["1 = 1"]
        params: dict[str, Any] = {"limit": limit}
        if facility_id:
            conditions.append("mission.facility_id = :facility_id")
            params["facility_id"] = facility_id

        rows = self.db.execute(
            text(
                f"""
                SELECT
                    mission.mission_id,
                    mission.facility_id,
                    facility.facility_name,
                    mission.window_start,
                    mission.window_end,
                    mission.status,
                    mission.appointments_at_risk,
                    mission.projected_sla_misses_before,
                    mission.projected_sla_misses_after,
                    mission.estimated_net_savings,
                    mission.realized_sla_misses,
                    mission.realized_minutes_saved,
                    mission.realized_net_savings,
                    mission.outcome_sample_size,
                    mission.outcome_captured_at,
                    mission.optimizer_version,
                    mission.created_at
                FROM optimization_missions mission
                JOIN facilities facility
                  ON facility.facility_id = mission.facility_id
                WHERE {' AND '.join(conditions)}
                ORDER BY mission.created_at DESC, mission.mission_id DESC
                LIMIT :limit;
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def update_status(
        self,
        mission_id: int,
        status: str,
    ) -> dict[str, Any]:
        allowed_transitions = {
            "Proposed": {"Accepted", "Dismissed"},
            "Accepted": {"In Progress", "Completed", "Dismissed"},
            "In Progress": {"Completed", "Dismissed"},
            "Completed": set(),
            "Dismissed": set(),
        }

        current = self.db.execute(
            text(
                """
                SELECT status
                FROM optimization_missions
                WHERE mission_id = :mission_id;
                """
            ),
            {"mission_id": mission_id},
        ).scalar_one_or_none()

        if current is None:
            raise ValueError(
                f"Optimization mission {mission_id} does not exist."
            )

        if status != current and status not in allowed_transitions.get(
            str(current),
            set(),
        ):
            raise ValueError(
                f"Mission {mission_id} cannot transition from "
                f"{current} to {status}."
            )

        timestamp_column = {
            "Accepted": "accepted_at",
            "In Progress": "started_at",
            "Completed": "completed_at",
        }.get(status)

        timestamp_sql = (
            f", {timestamp_column} = COALESCE({timestamp_column}, NOW())"
            if timestamp_column
            else ""
        )

        row = self.db.execute(
            text(
                f"""
                UPDATE optimization_missions
                SET status = :status
                    {timestamp_sql}
                WHERE mission_id = :mission_id
                RETURNING
                    mission_id,
                    facility_id,
                    window_start,
                    window_end,
                    status,
                    appointments_at_risk,
                    projected_sla_misses_before,
                    projected_sla_misses_after,
                    estimated_net_savings,
                    realized_sla_misses,
                    realized_minutes_saved,
                    realized_net_savings,
                    outcome_sample_size,
                    outcome_captured_at,
                    optimizer_version,
                    created_at,
                    accepted_at,
                    started_at,
                    completed_at;
                """
            ),
            {
                "mission_id": mission_id,
                "status": status,
            },
        ).mappings().one()

        action_timestamp_sql = (
            f", {timestamp_column} = COALESCE({timestamp_column}, NOW())"
            if timestamp_column
            else ""
        )
        self.db.execute(
            text(
                f"""
                UPDATE optimization_mission_actions
                SET status = :status
                    {action_timestamp_sql}
                WHERE mission_id = :mission_id;
                """
            ),
            {
                "mission_id": mission_id,
                "status": status,
            },
        )

        if status == "Accepted":
            self._propagate_accepted_mission(mission_id)
        elif status == "In Progress":
            self.db.execute(
                text(
                    """
                    UPDATE appointment_recommendations
                    SET status = 'Accepted'
                    WHERE optimization_mission_id = :mission_id;
                    """
                ),
                {"mission_id": mission_id},
            )
            self.db.execute(
                text(
                    """
                    UPDATE recommendation_actions action
                    SET status = 'In Progress'
                    FROM appointment_recommendations recommendation
                    WHERE recommendation.recommendation_id =
                          action.recommendation_id
                      AND recommendation.optimization_mission_id =
                          :mission_id;
                    """
                ),
                {"mission_id": mission_id},
            )
        elif status == "Completed":
            self.db.execute(
                text(
                    """
                    UPDATE appointment_recommendations
                    SET status = 'Completed'
                    WHERE optimization_mission_id = :mission_id;
                    """
                ),
                {"mission_id": mission_id},
            )
            self.db.execute(
                text(
                    """
                    UPDATE recommendation_actions action
                    SET status = 'Completed'
                    FROM appointment_recommendations recommendation
                    WHERE recommendation.recommendation_id =
                          action.recommendation_id
                      AND recommendation.optimization_mission_id =
                          :mission_id;
                    """
                ),
                {"mission_id": mission_id},
            )
            self._capture_realized_outcomes(mission_id)
        elif status == "Dismissed":
            self.db.execute(
                text(
                    """
                    UPDATE appointment_recommendations
                    SET status = 'Rejected'
                    WHERE optimization_mission_id = :mission_id;
                    """
                ),
                {"mission_id": mission_id},
            )
            self.db.execute(
                text(
                    """
                    UPDATE recommendation_actions action
                    SET status = 'Rejected'
                    FROM appointment_recommendations recommendation
                    WHERE recommendation.recommendation_id =
                          action.recommendation_id
                      AND recommendation.optimization_mission_id =
                          :mission_id;
                    """
                ),
                {"mission_id": mission_id},
            )

        self.db.commit()
        return {
            **dict(row),
            "appointment_plan": self.get_mission_plan(mission_id),
        }

    def _capture_realized_outcomes(self, mission_id: int) -> dict[str, Any]:
        """Capture observed performance without treating missing actuals as success."""
        rows = self.db.execute(
            text(
                """
                SELECT
                    ma.appt_id,
                    ma.baseline_projected_turn_minutes,
                    a.actual_turn_time_minutes,
                    a.actual_sla_missed,
                    a.sla_minutes,
                    a.detention_cost_per_hour,
                    COALESCE((
                        SELECT SUM(x.estimated_action_cost)
                        FROM optimization_mission_actions x
                        WHERE x.mission_id = :mission_id
                          AND x.appt_id = ma.appt_id
                    ), 0) AS action_cost
                FROM optimization_mission_appointments ma
                JOIN appointments a ON a.appt_id = ma.appt_id
                WHERE ma.mission_id = :mission_id
                  AND a.actual_turn_time_minutes IS NOT NULL;
                """
            ),
            {"mission_id": mission_id},
        ).mappings().all()

        misses = 0
        minutes_saved_total = 0.0
        savings_total = 0.0
        for row in rows:
            baseline = float(row["baseline_projected_turn_minutes"] or 0)
            actual = float(row["actual_turn_time_minutes"] or 0)
            sla = float(row["sla_minutes"] or 120)
            rate = float(row["detention_cost_per_hour"] or 0)
            action_cost = float(row["action_cost"] or 0)
            missed = (
                bool(row["actual_sla_missed"])
                if row["actual_sla_missed"] is not None
                else actual > sla
            )
            minutes_saved = max(0.0, baseline - actual)
            baseline_loss = max(0.0, baseline - sla) / 60.0 * rate
            actual_loss = max(0.0, actual - sla) / 60.0 * rate
            net_savings = baseline_loss - actual_loss - action_cost
            misses += int(missed)
            minutes_saved_total += minutes_saved
            savings_total += net_savings

            self.db.execute(
                text(
                    """
                    UPDATE optimization_mission_appointments
                    SET actual_turn_minutes = :actual,
                        actual_sla_missed = :missed,
                        realized_minutes_saved = :minutes_saved,
                        realized_net_savings = :net_savings
                    WHERE mission_id = :mission_id
                      AND appt_id = :appt_id;
                    """
                ),
                {
                    "mission_id": mission_id,
                    "appt_id": row["appt_id"],
                    "actual": round(actual, 2),
                    "missed": missed,
                    "minutes_saved": round(minutes_saved, 2),
                    "net_savings": round(net_savings, 2),
                },
            )

        outcome = self.db.execute(
            text(
                """
                UPDATE optimization_missions
                SET realized_sla_misses = :misses,
                    realized_minutes_saved = :minutes_saved,
                    realized_net_savings = :net_savings,
                    outcome_sample_size = :sample_size,
                    outcome_captured_at = NOW()
                WHERE mission_id = :mission_id
                RETURNING realized_sla_misses,
                          realized_minutes_saved,
                          realized_net_savings,
                          outcome_sample_size,
                          outcome_captured_at;
                """
            ),
            {
                "mission_id": mission_id,
                "misses": misses if rows else None,
                "minutes_saved": round(minutes_saved_total, 2) if rows else None,
                "net_savings": round(savings_total, 2) if rows else None,
                "sample_size": len(rows),
            },
        ).mappings().one()
        self._refresh_action_effectiveness_profiles()

        return dict(outcome)

    def _refresh_action_effectiveness_profiles(
        self,
    ) -> None:
        """Rebuild contextual action-effectiveness profiles from actuals.

        A profile represents an action combination in a specific operating
        context. Confidence is sample_size / (sample_size + 10), capped later
        by the optimizer so learned behavior remains conservative.
        """
        self.db.execute(
            text(
                """
                WITH mission_actions AS (
                    SELECT
                        action.mission_id,
                        action.appt_id,
                        string_agg(
                            DISTINCT action.action_code,
                            '+'
                            ORDER BY action.action_code
                        ) AS action_signature
                    FROM optimization_mission_actions action
                    JOIN optimization_missions mission
                      ON mission.mission_id = action.mission_id
                    WHERE mission.status = 'Completed'
                    GROUP BY action.mission_id, action.appt_id
                ),
                samples AS (
                    SELECT
                        appointment.facility_id,
                        mission_actions.action_signature,
                        COALESCE(
                            appointment.appointment_type,
                            'Unknown'
                        ) AS appointment_type,
                        COALESCE(
                            appointment.load_type,
                            'Unknown'
                        ) AS load_type,
                        COALESCE(
                            (
                                SELECT CASE
                                    WHEN BOOL_OR(
                                        product.temperature_zone = 'Frozen'
                                    ) THEN 'Frozen'
                                    WHEN BOOL_OR(
                                        product.temperature_zone = 'Chilled'
                                    ) THEN 'Chilled'
                                    ELSE 'Ambient'
                                END
                                FROM appointment_products line
                                JOIN products product
                                  ON product.product_id = line.product_id
                                WHERE line.appt_id = appointment.appt_id
                            ),
                            'Ambient'
                        ) AS temperature_zone,
                        CASE
                            WHEN COALESCE(
                                appointment.pallet_count,
                                0
                            ) < 10 THEN '<10'
                            WHEN appointment.pallet_count < 20
                                THEN '10-19'
                            WHEN appointment.pallet_count < 30
                                THEN '20-29'
                            WHEN appointment.pallet_count < 40
                                THEN '30-39'
                            ELSE '40+'
                        END AS pallet_band,
                        CASE
                            WHEN COALESCE(
                                allocation.dock_congestion_percent,
                                0
                            ) < 25 THEN 'Low'
                            WHEN allocation.dock_congestion_percent < 50
                                THEN 'Moderate'
                            WHEN allocation.dock_congestion_percent < 75
                                THEN 'High'
                            ELSE 'Severe'
                        END AS congestion_band,
                        mission_appointment.actual_sla_missed,
                        mission_appointment.realized_minutes_saved,
                        mission_appointment.realized_net_savings,
                        mission.outcome_captured_at
                    FROM mission_actions
                    JOIN optimization_mission_appointments
                         mission_appointment
                      ON mission_appointment.mission_id =
                         mission_actions.mission_id
                     AND mission_appointment.appt_id =
                         mission_actions.appt_id
                    JOIN optimization_missions mission
                      ON mission.mission_id =
                         mission_actions.mission_id
                    JOIN appointments appointment
                      ON appointment.appt_id =
                         mission_actions.appt_id
                    LEFT JOIN appointment_resource_allocations allocation
                      ON allocation.appt_id =
                         appointment.appt_id
                    WHERE mission_appointment.actual_turn_minutes
                          IS NOT NULL
                ),
                aggregated AS (
                    SELECT
                        facility_id,
                        action_signature,
                        appointment_type,
                        load_type,
                        temperature_zone,
                        pallet_band,
                        congestion_band,
                        COUNT(*)::INTEGER AS sample_size,
                        AVG(
                            CASE
                                WHEN actual_sla_missed = FALSE
                                    THEN 1.0
                                ELSE 0.0
                            END
                        ) AS sla_success_rate,
                        AVG(
                            COALESCE(
                                realized_minutes_saved,
                                0
                            )
                        ) AS avg_realized_minutes_saved,
                        AVG(
                            COALESCE(
                                realized_net_savings,
                                0
                            )
                        ) AS avg_realized_net_savings,
                        MAX(outcome_captured_at) AS last_outcome_at
                    FROM samples
                    GROUP BY
                        facility_id,
                        action_signature,
                        appointment_type,
                        load_type,
                        temperature_zone,
                        pallet_band,
                        congestion_band
                )
                INSERT INTO optimization_action_effectiveness (
                    facility_id,
                    action_signature,
                    appointment_type,
                    load_type,
                    temperature_zone,
                    pallet_band,
                    congestion_band,
                    sample_size,
                    sla_success_rate,
                    avg_realized_minutes_saved,
                    avg_realized_net_savings,
                    confidence_weight,
                    last_outcome_at,
                    updated_at
                )
                SELECT
                    facility_id,
                    action_signature,
                    appointment_type,
                    load_type,
                    temperature_zone,
                    pallet_band,
                    congestion_band,
                    sample_size,
                    sla_success_rate,
                    avg_realized_minutes_saved,
                    avg_realized_net_savings,
                    sample_size::NUMERIC
                        / (sample_size + 10.0),
                    last_outcome_at,
                    NOW()
                FROM aggregated
                ON CONFLICT (
                    facility_id,
                    action_signature,
                    appointment_type,
                    load_type,
                    temperature_zone,
                    pallet_band,
                    congestion_band
                )
                DO UPDATE SET
                    sample_size = EXCLUDED.sample_size,
                    sla_success_rate =
                        EXCLUDED.sla_success_rate,
                    avg_realized_minutes_saved =
                        EXCLUDED.avg_realized_minutes_saved,
                    avg_realized_net_savings =
                        EXCLUDED.avg_realized_net_savings,
                    confidence_weight =
                        EXCLUDED.confidence_weight,
                    last_outcome_at =
                        EXCLUDED.last_outcome_at,
                    updated_at = NOW();
                """
            )
        )

    def action_effectiveness_summary(
        self,
        *,
        facility_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conditions = ["1 = 1"]
        params: dict[str, Any] = {"limit": limit}
        if facility_id:
            conditions.append(
                "facility_id = :facility_id"
            )
            params["facility_id"] = facility_id

        rows = self.db.execute(
            text(
                f"""
                SELECT
                    facility_id,
                    action_signature,
                    appointment_type,
                    load_type,
                    temperature_zone,
                    pallet_band,
                    congestion_band,
                    sample_size,
                    ROUND(
                        sla_success_rate * 100,
                        1
                    ) AS sla_success_percent,
                    ROUND(
                        avg_realized_minutes_saved,
                        1
                    ) AS avg_realized_minutes_saved,
                    ROUND(
                        avg_realized_net_savings,
                        2
                    ) AS avg_realized_net_savings,
                    ROUND(
                        confidence_weight * 100,
                        1
                    ) AS confidence_percent,
                    last_outcome_at,
                    updated_at
                FROM optimization_action_effectiveness
                WHERE {' AND '.join(conditions)}
                ORDER BY
                    sample_size DESC,
                    confidence_weight DESC,
                    avg_realized_minutes_saved DESC
                LIMIT :limit;
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def refresh_realized_outcomes(self, mission_id: int) -> dict[str, Any]:
        status = self.db.execute(
            text("SELECT status FROM optimization_missions WHERE mission_id = :mission_id"),
            {"mission_id": mission_id},
        ).scalar_one_or_none()
        if status is None:
            raise ValueError(f"Optimization mission {mission_id} does not exist.")
        if str(status) != "Completed":
            raise ValueError("Realized outcomes are available after the mission is completed.")
        outcome = self._capture_realized_outcomes(mission_id)
        self.db.commit()
        return {
            "mission_id": mission_id,
            "status": str(status),
            **outcome,
            "appointment_plan": self.get_mission_plan(mission_id),
        }

    def _propagate_accepted_mission(
        self,
        mission_id: int,
    ) -> None:
        """Expose coordinated mission actions in each appointment drawer."""
        appointment_rows = self.db.execute(
            text(
                """
                SELECT
                    mission_appointment.appt_id,
                    mission_appointment.priority_order,
                    mission_appointment.baseline_projected_turn_minutes,
                    mission_appointment.optimized_projected_turn_minutes,
                    appointment.assigned_dock_id,
                    appointment.detention_cost_per_hour,
                    appointment.sla_minutes
                FROM optimization_mission_appointments mission_appointment
                JOIN appointments appointment
                  ON appointment.appt_id = mission_appointment.appt_id
                WHERE mission_appointment.mission_id = :mission_id
                ORDER BY mission_appointment.priority_order;
                """
            ),
            {"mission_id": mission_id},
        ).mappings().all()

        for appointment in appointment_rows:
            actions = self.db.execute(
                text(
                    """
                    SELECT
                        action_code,
                        action_description,
                        additional_loaders,
                        additional_forklifts,
                        staging_labor,
                        required_dock_id,
                        expected_minutes_saved,
                        estimated_action_cost
                    FROM optimization_mission_actions
                    WHERE mission_id = :mission_id
                      AND appt_id = :appt_id
                    ORDER BY sequence_number;
                    """
                ),
                {
                    "mission_id": mission_id,
                    "appt_id": appointment["appt_id"],
                },
            ).mappings().all()

            if not actions:
                continue

            baseline_turn = float(
                appointment["baseline_projected_turn_minutes"] or 0
            )
            optimized_turn = float(
                appointment["optimized_projected_turn_minutes"] or baseline_turn
            )
            sla_minutes = float(appointment["sla_minutes"] or 120)
            detention_rate = float(
                appointment["detention_cost_per_hour"] or 0
            )
            baseline_loss = (
                max(0.0, baseline_turn - sla_minutes)
                / 60.0
                * detention_rate
            )
            optimized_loss = (
                max(0.0, optimized_turn - sla_minutes)
                / 60.0
                * detention_rate
            )
            action_cost = sum(
                float(action["estimated_action_cost"] or 0)
                for action in actions
            )
            gross_savings = max(
                0.0,
                baseline_loss - optimized_loss,
            )
            net_savings = gross_savings - action_cost

            summary = "; ".join(
                str(action["action_description"])
                for action in actions
            )
            recommendation_id = self.db.execute(
                text(
                    """
                    INSERT INTO appointment_recommendations (
                        appt_id,
                        recommendation_type,
                        recommended_action,
                        recommended_dock_id,
                        recommended_sequence,
                        additional_labor,
                        estimated_loss_without_action,
                        estimated_cost_of_action,
                        estimated_savings,
                        status,
                        optimization_mission_id,
                        created_at
                    ) VALUES (
                        :appt_id,
                        'Coordinated Recovery Mission',
                        :recommended_action,
                        :recommended_dock_id,
                        :recommended_sequence,
                        :additional_labor,
                        :estimated_loss_without_action,
                        :estimated_cost_of_action,
                        :estimated_savings,
                        'Accepted',
                        :mission_id,
                        NOW()
                    )
                    ON CONFLICT (
                        optimization_mission_id,
                        appt_id
                    )
                    DO UPDATE SET
                        recommended_action =
                            EXCLUDED.recommended_action,
                        estimated_loss_without_action =
                            EXCLUDED.estimated_loss_without_action,
                        estimated_cost_of_action =
                            EXCLUDED.estimated_cost_of_action,
                        estimated_savings =
                            EXCLUDED.estimated_savings,
                        status = 'Accepted'
                    RETURNING recommendation_id;
                    """
                ),
                {
                    "appt_id": appointment["appt_id"],
                    "recommended_action": (
                        f"Mission #{mission_id}: {summary}"
                    ),
                    "recommended_dock_id":
                        appointment["assigned_dock_id"],
                    "recommended_sequence":
                        appointment["priority_order"],
                    "additional_labor": sum(
                        int(action["additional_loaders"] or 0)
                        + int(action["staging_labor"] or 0)
                        for action in actions
                    ),
                    "estimated_loss_without_action":
                        round(baseline_loss, 2),
                    "estimated_cost_of_action":
                        round(action_cost, 2),
                    "estimated_savings":
                        round(net_savings, 2),
                    "mission_id": mission_id,
                },
            ).scalar_one()

            self.db.execute(
                text(
                    """
                    DELETE FROM recommendation_actions
                    WHERE recommendation_id = :recommendation_id;
                    """
                ),
                {"recommendation_id": recommendation_id},
            )

            for sequence_number, action in enumerate(
                actions,
                start=1,
            ):
                action_code = str(action["action_code"])
                title = {
                    "ADD_LOADER":
                        "Assign one additional loader",
                    "ADD_FORKLIFT":
                        "Reserve one additional forklift",
                    "PRE_STAGE_PRODUCTS":
                        "Pre-stage appointment products",
                    "REASSIGN_DOCK":
                        "Move appointment to recovery dock",
                }.get(
                    action_code,
                    action_code.replace("_", " ").title(),
                )
                self.db.execute(
                    text(
                        """
                        INSERT INTO recommendation_actions (
                            recommendation_id,
                            sequence_number,
                            action_code,
                            action_title,
                            action_description,
                            owner_role,
                            estimated_minutes_saved,
                            additional_loaders,
                            additional_forklifts,
                            required_dock_id,
                            estimated_action_cost,
                            status,
                            created_at
                        ) VALUES (
                            :recommendation_id,
                            :sequence_number,
                            :action_code,
                            :action_title,
                            :action_description,
                            'Warehouse Operations',
                            :estimated_minutes_saved,
                            :additional_loaders,
                            :additional_forklifts,
                            :required_dock_id,
                            :estimated_action_cost,
                            'Accepted',
                            NOW()
                        );
                        """
                    ),
                    {
                        "recommendation_id": recommendation_id,
                        "sequence_number": sequence_number,
                        "action_code": action_code,
                        "action_title": title,
                        "action_description":
                            action["action_description"],
                        "estimated_minutes_saved": int(
                            round(
                                float(
                                    action[
                                        "expected_minutes_saved"
                                    ]
                                    or 0
                                )
                            )
                        ),
                        "additional_loaders":
                            action["additional_loaders"],
                        "additional_forklifts":
                            action["additional_forklifts"],
                        "required_dock_id":
                            action["required_dock_id"],
                        "estimated_action_cost":
                            action["estimated_action_cost"],
                    },
                )

    def get_mission_plan(
        self,
        mission_id: int,
    ) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    mission_appointment.appt_id,
                    mission_appointment.priority_order,
                    mission_appointment.baseline_risk_score,
                    mission_appointment.baseline_projected_turn_minutes,
                    mission_appointment.optimized_projected_turn_minutes,
                    mission_appointment.sla_recovered,
                    mission_appointment.actual_turn_minutes,
                    mission_appointment.actual_sla_missed,
                    mission_appointment.realized_minutes_saved,
                    mission_appointment.realized_net_savings,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'mission_action_id',
                                    action.mission_action_id,
                                'sequence_number',
                                    action.sequence_number,
                                'action_code',
                                    action.action_code,
                                'action_description',
                                    action.action_description,
                                'additional_loaders',
                                    action.additional_loaders,
                                'additional_forklifts',
                                    action.additional_forklifts,
                                'staging_labor',
                                    action.staging_labor,
                                'required_dock_id',
                                    action.required_dock_id,
                                'expected_minutes_saved',
                                    action.expected_minutes_saved,
                                'estimated_action_cost',
                                    action.estimated_action_cost,
                                'status',
                                    action.status
                            )
                            ORDER BY action.sequence_number
                        ) FILTER (
                            WHERE action.mission_action_id IS NOT NULL
                        ),
                        '[]'::json
                    ) AS actions
                FROM optimization_mission_appointments
                    mission_appointment
                LEFT JOIN optimization_mission_actions action
                  ON action.mission_id =
                     mission_appointment.mission_id
                 AND action.appt_id =
                     mission_appointment.appt_id
                WHERE mission_appointment.mission_id =
                      :mission_id
                GROUP BY
                        mission_appointment.appt_id,
                        mission_appointment.priority_order,
                        mission_appointment.baseline_risk_score,
                        mission_appointment.baseline_projected_turn_minutes,
                        mission_appointment.optimized_projected_turn_minutes,
                        mission_appointment.sla_recovered,
                        mission_appointment.actual_turn_minutes,
                        mission_appointment.actual_sla_missed,
                        mission_appointment.realized_minutes_saved,
                        mission_appointment.realized_net_savings
                ORDER BY mission_appointment.priority_order;
                """
            ),
            {"mission_id": mission_id},
        ).mappings().all()
        return [dict(row) for row in rows]


    def _load_candidates(
        self,
        *,
        facility_id: str | None,
        customer_id: str | None,
        carrier_id: str | None,
        appointment_type: str | None,
        window_start: datetime,
        window_end: datetime,
    ) -> list[dict[str, Any]]:
        conditions = [
            "appointment.appt_id LIKE 'DEMO%'",
            "appointment.status NOT IN ('Completed', 'Cancelled')",
            "appointment.scheduled_time >= :window_start",
            "appointment.scheduled_time < :window_end",
        ]
        params: dict[str, Any] = {
            "window_start": window_start,
            "window_end": window_end,
        }

        if facility_id:
            conditions.append("appointment.facility_id = :facility_id")
            params["facility_id"] = facility_id
        if customer_id:
            conditions.append("appointment.customer_id = :customer_id")
            params["customer_id"] = customer_id
        if carrier_id:
            conditions.append("appointment.carrier_id = :carrier_id")
            params["carrier_id"] = carrier_id
        if appointment_type:
            conditions.append(
                "LOWER(appointment.appointment_type) = LOWER(:appointment_type)"
            )
            params["appointment_type"] = appointment_type

        rows = self.db.execute(
            text(
                f"""
                WITH latest_predictions AS (
                    SELECT DISTINCT ON (prediction.appt_id)
                        prediction.appt_id,
                        prediction.predicted_delay_minutes,
                        prediction.predicted_duration_minutes,
                        prediction.sla_miss_probability,
                        prediction.sla_recovery_probability,
                        prediction.turn_risk_score,
                        prediction.predicted_missed,
                        prediction.model_version
                    FROM appointment_predictions prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                )
                SELECT
                    appointment.appt_id,
                    appointment.facility_id,
                    facility.facility_name,
                    appointment.customer_id,
                    appointment.customer_name,
                    appointment.carrier_id,
                    carrier.carrier_name,
                    appointment.scheduled_time,
                    appointment.assigned_dock_id,
                    dock.dock_name,
                    appointment.appointment_type,
                    appointment.pallet_count,
                    appointment.sku_count,
                    appointment.sla_minutes,
                    appointment.detention_cost_per_hour,

                    prediction.predicted_delay_minutes,
                    prediction.predicted_duration_minutes,
                    prediction.sla_miss_probability,
                    prediction.sla_recovery_probability,
                    prediction.turn_risk_score,
                    prediction.predicted_missed,
                    prediction.model_version,

                    allocation.planned_loaders,
                    allocation.planned_forklifts,
                    allocation.planned_staging_labor,
                    allocation.dock_congestion_percent,
                    allocation.labor_utilization_percent,
                    allocation.forklift_utilization_percent,

                    profile.base_loader_capacity,
                    profile.base_forklift_capacity,

                    COALESCE(
                        (
                            SELECT CASE
                                WHEN BOOL_OR(product.temperature_zone = 'Frozen')
                                    THEN 'Frozen'
                                WHEN BOOL_OR(product.temperature_zone = 'Chilled')
                                    THEN 'Chilled'
                                ELSE 'Ambient'
                            END
                            FROM appointment_products line
                            JOIN products product
                              ON product.product_id = line.product_id
                            WHERE line.appt_id = appointment.appt_id
                        ),
                        'Ambient'
                    ) AS required_temperature_zone

                FROM appointments appointment
                JOIN latest_predictions prediction
                  ON prediction.appt_id = appointment.appt_id
                JOIN facilities facility
                  ON facility.facility_id = appointment.facility_id
                LEFT JOIN carriers carrier
                  ON carrier.carrier_id = appointment.carrier_id
                LEFT JOIN docks dock
                  ON dock.dock_id = appointment.assigned_dock_id
                JOIN appointment_resource_allocations allocation
                  ON allocation.appt_id = appointment.appt_id
                JOIN facility_operational_profiles profile
                  ON profile.facility_id = appointment.facility_id
                WHERE {' AND '.join(conditions)}
                  AND (
                      prediction.predicted_missed = TRUE
                      OR prediction.turn_risk_score >= 60
                      OR (
                          GREATEST(
                              COALESCE(prediction.predicted_delay_minutes, 0),
                              0
                          )
                          + COALESCE(prediction.predicted_duration_minutes, 0)
                      ) > appointment.sla_minutes
                  )
                ORDER BY
                    appointment.facility_id,
                    prediction.predicted_missed DESC,
                    prediction.turn_risk_score DESC,
                    prediction.sla_miss_probability DESC,
                    appointment.scheduled_time;
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def _shift_name_for_hour(hour: int) -> str:
        if 6 <= hour < 14:
            return "First"
        if 14 <= hour < 22:
            return "Second"
        return "Third"

    def _load_hourly_resource_snapshot(
        self,
        facility_id: str,
        window_start: datetime,
        window_end: datetime,
        *,
        fallback_loader_capacity: int,
        fallback_forklift_capacity: int,
    ) -> dict[datetime, dict[str, int]]:
        """Build real resource capacity/headroom for every operating hour.

        Loader capacity comes from labor_shifts. Forklift capacity is the
        smaller of available forklift operators and physically available
        forklift-class equipment. Existing appointment plans plus Accepted /
        In Progress optimization missions are treated as committed demand.
        """
        labor_rows = self.db.execute(
            text(
                """
                SELECT
                    shift_date,
                    shift_name,
                    COALESCE(
                        MAX(available_headcount)
                        FILTER (WHERE role = 'Loader'),
                        0
                    )::INTEGER AS loader_capacity,
                    COALESCE(
                        MAX(
                            GREATEST(
                                available_headcount,
                                forklift_certified_count
                            )
                        )
                        FILTER (
                            WHERE role = 'Forklift Operator'
                        ),
                        0
                    )::INTEGER AS forklift_operator_capacity,
                    COALESCE(
                        MAX(available_headcount)
                        FILTER (WHERE role = 'Dock Coordinator'),
                        0
                    )::INTEGER AS dock_coordinator_capacity
                FROM labor_shifts
                WHERE facility_id = :facility_id
                  AND shift_date >= DATE(:window_start)
                  AND shift_date <= DATE(:window_end)
                GROUP BY shift_date, shift_name;
                """
            ),
            {
                "facility_id": facility_id,
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().all()

        labor_by_shift = {
            (
                row["shift_date"],
                str(row["shift_name"]),
            ): {
                "loaders": int(
                    row["loader_capacity"] or 0
                ),
                "forklift_operators": int(
                    row[
                        "forklift_operator_capacity"
                    ]
                    or 0
                ),
                "dock_coordinators": int(
                    row["dock_coordinator_capacity"]
                    or 0
                ),
            }
            for row in labor_rows
        }

        equipment_rows = self.db.execute(
            text(
                """
                SELECT
                    equipment_id,
                    equipment_type,
                    status,
                    active
                FROM equipment
                WHERE facility_id = :facility_id
                  AND active = TRUE
                  AND equipment_type IN (
                      'Forklift',
                      'Reach Truck',
                      'Clamp Truck'
                  );
                """
            ),
            {"facility_id": facility_id},
        ).mappings().all()

        available_forklift_equipment = sum(
            1
            for row in equipment_rows
            if str(row["status"]).lower()
            == "available"
        )

        usage_rows = self.db.execute(
            text(
                """
                SELECT
                    date_trunc(
                        'hour',
                        appointment.scheduled_time
                    ) AS hour_bucket,
                    COALESCE(
                        SUM(
                            allocation.planned_loaders
                            + allocation.planned_staging_labor
                        ),
                        0
                    )::INTEGER AS loaders_used,
                    COALESCE(
                        SUM(
                            allocation.planned_forklifts
                        ),
                        0
                    )::INTEGER AS forklifts_used
                FROM appointments appointment
                JOIN appointment_resource_allocations allocation
                  ON allocation.appt_id =
                     appointment.appt_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND appointment.facility_id =
                      :facility_id
                  AND appointment.status NOT IN (
                      'Completed',
                      'Cancelled'
                  )
                  AND appointment.scheduled_time >=
                      :window_start
                  AND appointment.scheduled_time <
                      :window_end
                GROUP BY date_trunc(
                    'hour',
                    appointment.scheduled_time
                );
                """
            ),
            {
                "facility_id": facility_id,
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().all()

        usage = {
            row["hour_bucket"]: {
                "loaders": int(
                    row["loaders_used"] or 0
                ),
                "forklifts": int(
                    row["forklifts_used"] or 0
                ),
            }
            for row in usage_rows
        }

        mission_rows = self.db.execute(
            text(
                """
                SELECT
                    date_trunc(
                        'hour',
                        appointment.scheduled_time
                    ) AS hour_bucket,
                    COALESCE(
                        SUM(
                            action.additional_loaders
                            + action.staging_labor
                        ),
                        0
                    )::INTEGER AS mission_loaders,
                    COALESCE(
                        SUM(
                            action.additional_forklifts
                        ),
                        0
                    )::INTEGER AS mission_forklifts
                FROM optimization_mission_actions action
                JOIN optimization_missions mission
                  ON mission.mission_id =
                     action.mission_id
                JOIN appointments appointment
                  ON appointment.appt_id =
                     action.appt_id
                WHERE mission.facility_id =
                      :facility_id
                  AND mission.status IN (
                      'Accepted',
                      'In Progress'
                  )
                  AND appointment.scheduled_time >=
                      :window_start
                  AND appointment.scheduled_time <
                      :window_end
                GROUP BY date_trunc(
                    'hour',
                    appointment.scheduled_time
                );
                """
            ),
            {
                "facility_id": facility_id,
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().all()

        committed = {
            row["hour_bucket"]: {
                "loaders": int(
                    row["mission_loaders"] or 0
                ),
                "forklifts": int(
                    row["mission_forklifts"] or 0
                ),
            }
            for row in mission_rows
        }

        snapshot: dict[
            datetime,
            dict[str, int],
        ] = {}
        bucket = window_start.replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        final_bucket = window_end.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        while bucket <= final_bucket:
            shift_name = self._shift_name_for_hour(
                bucket.hour
            )
            shift = labor_by_shift.get(
                (
                    bucket.date(),
                    shift_name,
                )
            )

            loader_capacity = (
                shift["loaders"]
                if shift
                and shift["loaders"] > 0
                else fallback_loader_capacity
            )
            forklift_operator_capacity = (
                shift["forklift_operators"]
                if shift
                and shift[
                    "forklift_operators"
                ] > 0
                else fallback_forklift_capacity
            )
            staging_capacity = (
                shift["dock_coordinators"]
                if shift
                and shift[
                    "dock_coordinators"
                ] > 0
                else max(
                    1,
                    loader_capacity // 4,
                )
            )

            forklift_capacity = max(
                0,
                min(
                    forklift_operator_capacity,
                    available_forklift_equipment
                    if available_forklift_equipment
                    > 0
                    else fallback_forklift_capacity,
                ),
            )

            used = usage.get(
                bucket,
                {
                    "loaders": 0,
                    "forklifts": 0,
                },
            )
            reserved = committed.get(
                bucket,
                {
                    "loaders": 0,
                    "forklifts": 0,
                },
            )

            snapshot[bucket] = {
                "loader_capacity":
                    loader_capacity,
                "forklift_capacity":
                    forklift_capacity,
                "staging_capacity":
                    staging_capacity,
                "loaders_used":
                    used["loaders"],
                "forklifts_used":
                    used["forklifts"],
                "mission_loaders_reserved":
                    reserved["loaders"],
                "mission_forklifts_reserved":
                    reserved["forklifts"],
                "loaders": max(
                    0,
                    loader_capacity
                    - used["loaders"]
                    - reserved["loaders"],
                ),
                "forklifts": max(
                    0,
                    forklift_capacity
                    - used["forklifts"]
                    - reserved["forklifts"],
                ),
                "staging": max(
                    0,
                    staging_capacity
                    - reserved["loaders"],
                ),
            }
            bucket += timedelta(hours=1)

        return snapshot

    def _load_dock_snapshot(
        self,
        facility_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, list[tuple[datetime, datetime, str]]],
    ]:
        docks = [
            dict(row)
            for row in self.db.execute(
                text(
                    """
                    SELECT
                        dock_id,
                        dock_name,
                        dock_type,
                        temperature_zone
                    FROM docks
                    WHERE facility_id = :facility_id
                      AND active = TRUE
                    ORDER BY dock_name, dock_id;
                    """
                ),
                {"facility_id": facility_id},
            ).mappings().all()
        ]

        occupancy_rows = self.db.execute(
            text(
                """
                WITH latest_predictions AS (
                    SELECT DISTINCT ON (
                        prediction.appt_id
                    )
                        prediction.appt_id,
                        prediction.predicted_delay_minutes,
                        prediction.predicted_duration_minutes
                    FROM appointment_predictions prediction
                    ORDER BY
                        prediction.appt_id,
                        prediction.generated_at DESC,
                        prediction.prediction_id DESC
                ),
                accepted_dock_moves AS (
                    SELECT DISTINCT ON (
                        action.appt_id
                    )
                        action.appt_id,
                        action.required_dock_id
                    FROM optimization_mission_actions action
                    JOIN optimization_missions mission
                      ON mission.mission_id =
                         action.mission_id
                    WHERE action.action_code =
                          'REASSIGN_DOCK'
                      AND mission.status IN (
                          'Accepted',
                          'In Progress'
                      )
                    ORDER BY
                        action.appt_id,
                        mission.created_at DESC,
                        action.mission_action_id DESC
                )
                SELECT
                    appointment.appt_id,
                    COALESCE(
                        dock_move.required_dock_id,
                        appointment.assigned_dock_id
                    ) AS dock_id,
                    appointment.scheduled_time
                    + (
                        GREATEST(
                            COALESCE(
                                prediction.predicted_delay_minutes,
                                0
                            ),
                            0
                        )
                        * INTERVAL '1 minute'
                    ) AS service_start,
                    appointment.scheduled_time
                    + (
                        (
                            GREATEST(
                                COALESCE(
                                    prediction.predicted_delay_minutes,
                                    0
                                ),
                                0
                            )
                            + GREATEST(
                                COALESCE(
                                    prediction.predicted_duration_minutes,
                                    30
                                ),
                                30
                            )
                        )
                        * INTERVAL '1 minute'
                    ) AS service_end
                FROM appointments appointment
                JOIN latest_predictions prediction
                  ON prediction.appt_id =
                     appointment.appt_id
                LEFT JOIN accepted_dock_moves dock_move
                  ON dock_move.appt_id =
                     appointment.appt_id
                WHERE appointment.facility_id =
                      :facility_id
                  AND appointment.status NOT IN (
                      'Completed',
                      'Cancelled'
                  )
                  AND appointment.scheduled_time <
                      :window_end
                  AND appointment.scheduled_time
                      + INTERVAL '6 hours'
                      >= :window_start
                  AND COALESCE(
                      dock_move.required_dock_id,
                      appointment.assigned_dock_id
                  ) IS NOT NULL;
                """
            ),
            {
                "facility_id": facility_id,
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().all()

        occupancy: dict[
            str,
            list[
                tuple[
                    datetime,
                    datetime,
                    str,
                ]
            ],
        ] = defaultdict(list)
        for row in occupancy_rows:
            occupancy[
                str(row["dock_id"])
            ].append(
                (
                    row["service_start"],
                    row["service_end"],
                    str(row["appt_id"]),
                )
            )
        return docks, occupancy

    @staticmethod
    def _temperature_compatible(
        required_zone: str | None,
        dock_zone: str | None,
    ) -> bool:
        required = (
            required_zone or "Ambient"
        ).strip().lower()
        dock = (
            dock_zone or "Ambient"
        ).strip().lower()

        # Cold-chain appointments stay in their required zone.
        # Ambient freight can use ambient docks only so cold capacity
        # remains protected for temperature-controlled loads.
        return required == dock

    @staticmethod
    def _interval_overlaps(
        start_a: datetime,
        end_a: datetime,
        start_b: datetime,
        end_b: datetime,
    ) -> bool:
        return start_a < end_b and end_a > start_b

    def _find_recovery_dock(
        self,
        row: dict[str, Any],
        docks: list[dict[str, Any]],
        occupancy: dict[
            str,
            list[
                tuple[
                    datetime,
                    datetime,
                    str,
                ]
            ],
        ],
        *,
        service_start: datetime,
        service_end: datetime,
    ) -> dict[str, Any] | None:
        current_dock = row.get(
            "assigned_dock_id"
        )
        required_zone = str(
            row.get(
                "required_temperature_zone"
            )
            or "Ambient"
        )

        candidates: list[
            tuple[int, str, dict[str, Any]]
        ] = []
        for dock in docks:
            dock_id = str(dock["dock_id"])
            if dock_id == current_dock:
                continue
            if not self._temperature_compatible(
                required_zone,
                dock.get("temperature_zone"),
            ):
                continue

            conflicts = 0
            for (
                occupied_start,
                occupied_end,
                occupied_appt_id,
            ) in occupancy.get(
                dock_id,
                [],
            ):
                if (
                    occupied_appt_id
                    == row["appt_id"]
                ):
                    continue
                if self._interval_overlaps(
                    service_start,
                    service_end,
                    occupied_start,
                    occupied_end,
                ):
                    conflicts += 1

            candidates.append(
                (
                    conflicts,
                    str(
                        dock.get("dock_name")
                        or dock_id
                    ),
                    dock,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item[0],
                item[1],
            )
        )
        best = candidates[0]
        return best[2] if best[0] == 0 else None

    @staticmethod
    def _current_dock_has_conflict(
        row: dict[str, Any],
        occupancy: dict[
            str,
            list[
                tuple[
                    datetime,
                    datetime,
                    str,
                ]
            ],
        ],
        *,
        service_start: datetime,
        service_end: datetime,
    ) -> bool:
        dock_id = row.get(
            "assigned_dock_id"
        )
        if not dock_id:
            return True

        for (
            occupied_start,
            occupied_end,
            occupied_appt_id,
        ) in occupancy.get(
            str(dock_id),
            [],
        ):
            if (
                occupied_appt_id
                == row["appt_id"]
            ):
                continue
            if (
                service_start
                < occupied_end
                and service_end
                > occupied_start
            ):
                return True
        return False


    def _optimize_facility(
        self,
        facility_id: str,
        rows: list[dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
        *,
        max_extra_loaders_per_hour: int | None = None,
        max_extra_forklifts_per_hour: int | None = None,
        max_staging_labor_per_hour: int | None = None,
        allow_dock_reassignment: bool = True,
    ) -> dict[str, Any] | None:
        if not rows:
            return None

        fallback_loader_capacity = int(
            rows[0]["base_loader_capacity"]
            or 1
        )
        fallback_forklift_capacity = int(
            rows[0]["base_forklift_capacity"]
            or 1
        )

        resource_snapshot = (
            self._load_hourly_resource_snapshot(
                facility_id,
                window_start,
                window_end,
                fallback_loader_capacity=
                    fallback_loader_capacity,
                fallback_forklift_capacity=
                    fallback_forklift_capacity,
            )
        )
        docks, dock_occupancy = (
            self._load_dock_snapshot(
                facility_id,
                window_start,
                window_end,
            )
        )

        # Mission-level What-If limits never create capacity that does not
        # exist. They only constrain the real shift/equipment headroom.
        for values in resource_snapshot.values():
            if max_extra_loaders_per_hour is not None:
                values["loaders"] = min(
                    values["loaders"],
                    max_extra_loaders_per_hour,
                )
            if max_extra_forklifts_per_hour is not None:
                values["forklifts"] = min(
                    values["forklifts"],
                    max_extra_forklifts_per_hour,
                )
            if max_staging_labor_per_hour is not None:
                values["staging"] = min(
                    values["staging"],
                    max_staging_labor_per_hour,
                )

        effectiveness_profiles = (
            self._load_action_effectiveness(
                facility_id
            )
        )

        enriched = [
            self._enrich_candidate(row)
            for row in rows
        ]
        enriched.sort(
            key=lambda row: (
                not bool(
                    row["predicted_missed"]
                ),
                -float(
                    row["minutes_over_sla"]
                ),
                -float(
                    row["turn_risk_score"]
                ),
                -float(
                    row["baseline_exposure"]
                ),
                row["scheduled_time"],
            )
        )

        plan: list[dict[str, Any]] = []
        resource_shortages: list[str] = []

        for priority_order, row in enumerate(
            enriched,
            start=1,
        ):
            bucket = row[
                "scheduled_time"
            ].replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            available = (
                resource_snapshot.get(
                    bucket
                )
            )
            if available is None:
                available = {
                    "loaders":
                        fallback_loader_capacity,
                    "forklifts":
                        fallback_forklift_capacity,
                    "staging": max(
                        1,
                        fallback_loader_capacity
                        // 4,
                    ),
                    "loader_capacity":
                        fallback_loader_capacity,
                    "forklift_capacity":
                        fallback_forklift_capacity,
                    "staging_capacity":
                        max(
                            1,
                            fallback_loader_capacity
                            // 4,
                        ),
                    "loaders_used": 0,
                    "forklifts_used": 0,
                    "mission_loaders_reserved": 0,
                    "mission_forklifts_reserved": 0,
                }
                resource_snapshot[
                    bucket
                ] = available

            option = self._choose_option(
                row,
                available_loaders=
                    available["loaders"],
                available_forklifts=
                    available["forklifts"],
                effectiveness_profiles=
                    effectiveness_profiles,
            )

            # Staging is constrained separately by dock-coordinator
            # availability instead of silently consuming an unlimited loader.
            if (
                option.staging_labor
                > available["staging"]
            ):
                alternatives = [
                    candidate
                    for candidate in OPTIONS
                    if candidate.staging_labor == 0
                    and candidate.extra_loaders
                        <= available["loaders"]
                    and candidate.extra_forklifts
                        <= available["forklifts"]
                ]
                option = max(
                    alternatives,
                    key=lambda candidate:
                        self._option_evaluation(
                            row,
                            candidate,
                            learned_estimate=
                                self._learned_option_estimate(
                                    row,
                                    candidate,
                                    effectiveness_profiles,
                                ),
                        ),
                    default=OPTIONS[0],
                )

            available["loaders"] -= (
                option.extra_loaders
            )
            available["forklifts"] -= (
                option.extra_forklifts
            )
            available["staging"] -= (
                option.staging_labor
            )

            baseline_turn = float(
                row["baseline_turn_minutes"]
            )
            learned_estimate = (
                self._learned_option_estimate(
                    row,
                    option,
                    effectiveness_profiles,
                )
            )
            resource_minutes_saved = float(
                learned_estimate[
                    "minutes_saved"
                ]
            )

            service_start = (
                row["scheduled_time"]
                + timedelta(
                    minutes=max(
                        0.0,
                        float(
                            row.get(
                                "predicted_delay_minutes"
                            )
                            or 0
                        ),
                    )
                )
            )
            preliminary_end = (
                service_start
                + timedelta(
                    minutes=max(
                        30.0,
                        baseline_turn
                        - max(
                            0.0,
                            float(
                                row.get(
                                    "predicted_delay_minutes"
                                )
                                or 0
                            ),
                        )
                        - resource_minutes_saved,
                    )
                )
            )

            current_dock_conflict = (
                self._current_dock_has_conflict(
                    row,
                    dock_occupancy,
                    service_start=
                        service_start,
                    service_end=
                        preliminary_end,
                )
            )

            should_consider_dock_move = (
                current_dock_conflict
                or float(
                    row.get(
                        "dock_congestion_percent"
                    )
                    or 0
                )
                >= 50.0
                or not row.get(
                    "assigned_dock_id"
                )
            )
            recovery_dock = (
                self._find_recovery_dock(
                    row,
                    docks,
                    dock_occupancy,
                    service_start=
                        service_start,
                    service_end=
                        preliminary_end,
                )
                if (
                    allow_dock_reassignment
                    and should_consider_dock_move
                )
                else None
            )

            dock_minutes_saved = (
                8.0
                if recovery_dock
                is not None
                else 0.0
            )
            total_minutes_saved = (
                resource_minutes_saved
                + dock_minutes_saved
            )

            optimized_turn = max(
                30.0,
                baseline_turn
                - total_minutes_saved,
            )
            optimized_turn = min(
                baseline_turn,
                optimized_turn,
            )
            actual_minutes_saved = max(
                0.0,
                baseline_turn
                - optimized_turn,
            )
            sla_recovered = (
                optimized_turn
                <= float(
                    row["sla_minutes"]
                )
            )

            optimized_service_end = (
                service_start
                + timedelta(
                    minutes=max(
                        30.0,
                        optimized_turn
                        - max(
                            0.0,
                            float(
                                row.get(
                                    "predicted_delay_minutes"
                                )
                                or 0
                            ),
                        ),
                    )
                )
            )
            selected_dock_id = (
                str(
                    recovery_dock[
                        "dock_id"
                    ]
                )
                if recovery_dock
                else row.get(
                    "assigned_dock_id"
                )
            )
            selected_dock_name = (
                str(
                    recovery_dock.get(
                        "dock_name"
                    )
                    or recovery_dock[
                        "dock_id"
                    ]
                )
                if recovery_dock
                else row.get("dock_name")
            )

            if selected_dock_id:
                dock_occupancy[
                    str(
                        selected_dock_id
                    )
                ].append(
                    (
                        service_start,
                        optimized_service_end,
                        str(
                            row["appt_id"]
                        ),
                    )
                )

            detention_rate = float(
                row[
                    "detention_cost_per_hour"
                ]
                or 0
            )
            optimized_exposure = (
                max(
                    0.0,
                    optimized_turn
                    - float(
                        row["sla_minutes"]
                    ),
                )
                / 60.0
                * detention_rate
            )
            gross_savings = max(
                0.0,
                float(
                    row[
                        "baseline_exposure"
                    ]
                )
                - optimized_exposure,
            )

            dock_action_cost = (
                15.0
                if recovery_dock
                else 0.0
            )
            total_action_cost = (
                float(
                    option.action_cost
                )
                + dock_action_cost
            )
            net_savings = (
                gross_savings
                - total_action_cost
            )

            actions = (
                self._actions_for_option(
                    row,
                    option,
                    resource_minutes_saved,
                )
            )
            if recovery_dock:
                actions.append(
                    {
                        "action_code":
                            "REASSIGN_DOCK",
                        "action_description": (
                            "Move the appointment from "
                            f"{row.get('dock_name') or row.get('assigned_dock_id') or 'unassigned'} "
                            f"to {selected_dock_name}; the recovery dock is "
                            f"{row.get('required_temperature_zone') or 'Ambient'}-compatible "
                            "and has no overlapping active reservation."
                        ),
                        "additional_loaders":
                            0,
                        "additional_forklifts":
                            0,
                        "staging_labor": 0,
                        "required_dock_id":
                            selected_dock_id,
                        "expected_minutes_saved":
                            dock_minutes_saved,
                        "estimated_action_cost":
                            dock_action_cost,
                    }
                )

            if (
                not actions
                and float(
                    row[
                        "baseline_turn_minutes"
                    ]
                )
                > float(
                    row["sla_minutes"]
                )
            ):
                shortage_parts = []
                if available["loaders"] <= 0:
                    shortage_parts.append(
                        "loader"
                    )
                if (
                    available["forklifts"]
                    <= 0
                ):
                    shortage_parts.append(
                        "forklift"
                    )
                if (
                    bool(
                        row["complex_load"]
                    )
                    and available["staging"]
                    <= 0
                ):
                    shortage_parts.append(
                        "staging"
                    )
                if (
                    current_dock_conflict
                    and recovery_dock is None
                ):
                    shortage_parts.append(
                        "compatible dock"
                    )
                if shortage_parts:
                    resource_shortages.append(
                        f"{row['appt_id']}: no spare "
                        + ", ".join(
                            shortage_parts
                        )
                        + " capacity"
                    )

            plan.append(
                {
                    "appt_id":
                        row["appt_id"],
                    "scheduled_time":
                        row[
                            "scheduled_time"
                        ].isoformat(),
                    "dock_id":
                        selected_dock_id,
                    "dock_name":
                        selected_dock_name,
                    "original_dock_id":
                        row.get(
                            "assigned_dock_id"
                        ),
                    "original_dock_name":
                        row.get(
                            "dock_name"
                        ),
                    "required_temperature_zone":
                        row.get(
                            "required_temperature_zone"
                        ),
                    "baseline_risk_score":
                        int(
                            row[
                                "turn_risk_score"
                            ]
                            or 0
                        ),
                    "baseline_sla_miss_probability":
                        round(
                            float(
                                row[
                                    "sla_miss_probability"
                                ]
                                or 0
                            ),
                            4,
                        ),
                    "baseline_projected_turn_minutes":
                        round(
                            baseline_turn,
                            1,
                        ),
                    "optimized_projected_turn_minutes":
                        round(
                            optimized_turn,
                            1,
                        ),
                    "minutes_saved":
                        round(
                            actual_minutes_saved,
                            1,
                        ),
                    "sla_minutes":
                        int(
                            row[
                                "sla_minutes"
                            ]
                        ),
                    "sla_recovered":
                        bool(
                            sla_recovered
                        ),
                    "priority_order":
                        priority_order,
                    "baseline_exposure":
                        round(
                            float(
                                row[
                                    "baseline_exposure"
                                ]
                            ),
                            2,
                        ),
                    "optimized_exposure":
                        round(
                            optimized_exposure,
                            2,
                        ),
                    "gross_savings":
                        round(
                            gross_savings,
                            2,
                        ),
                    "action_cost":
                        round(
                            total_action_cost,
                            2,
                        ),
                    "net_savings":
                        round(
                            net_savings,
                            2,
                        ),
                    "learning_evidence": {
                        "source":
                            learned_estimate["source"],
                        "sample_size":
                            learned_estimate["sample_size"],
                        "confidence_weight":
                            learned_estimate[
                                "confidence_weight"
                            ],
                        "sla_success_rate":
                            learned_estimate[
                                "sla_success_rate"
                            ],
                        "historical_avg_net_savings":
                            learned_estimate[
                                "avg_realized_net_savings"
                            ],
                    },
                    "resource_bucket":
                        bucket.isoformat(),
                    "remaining_resource_headroom":
                        {
                            "loaders":
                                available[
                                    "loaders"
                                ],
                            "forklifts":
                                available[
                                    "forklifts"
                                ],
                            "staging":
                                available[
                                    "staging"
                                ],
                        },
                    "actions": actions,
                }
            )

        before_misses = sum(
            1
            for row in enriched
            if bool(
                row["predicted_missed"]
            )
            or float(
                row[
                    "baseline_turn_minutes"
                ]
            )
            > float(
                row["sla_minutes"]
            )
        )
        after_misses = sum(
            1
            for item in plan
            if not item[
                "sla_recovered"
            ]
        )
        recovered = max(
            0,
            before_misses
            - after_misses,
        )
        minutes_saved = sum(
            float(
                item["minutes_saved"]
            )
            for item in plan
        )
        net_savings = sum(
            float(
                item["net_savings"]
            )
            for item in plan
        )

        facility_name = str(
            rows[0].get(
                "facility_name"
            )
            or facility_id
        )
        primary = (
            plan[0]
            if plan
            else None
        )
        actionable = [
            item
            for item in plan
            if item["actions"]
        ]
        recommended_actions = [
            self._summary_action(
                item
            )
            for item
            in actionable[:5]
        ]
        if not recommended_actions:
            recommended_actions = [
                "Keep the current plan; real shift, equipment and dock capacity do not support a beneficial recovery move."
            ]

        recovery_probability = (
            round(
                recovered
                / before_misses
                * 100,
                1,
            )
            if before_misses > 0
            else 100.0
        )
        priority_score = min(
            100,
            max(
                int(
                    float(
                        row[
                            "turn_risk_score"
                        ]
                        or 0
                    )
                )
                for row in rows
            )
            + min(
                15,
                before_misses * 2,
            ),
        )
        severity = (
            "Critical"
            if before_misses >= 3
            or priority_score >= 90
            else "High"
            if before_misses > 0
            else "Warning"
        )

        capacity_by_hour = [
            {
                "hour":
                    bucket.isoformat(),
                "loaders_available":
                    values["loader_capacity"],
                "forklifts_available":
                    values[
                        "forklift_capacity"
                    ],
                "staging_available":
                    values[
                        "staging_capacity"
                    ],
                "loader_headroom":
                    values["loaders"],
                "forklift_headroom":
                    values["forklifts"],
                "staging_headroom":
                    values["staging"],
            }
            for bucket, values
            in sorted(
                resource_snapshot.items()
            )
            if window_start
            <= bucket
            < window_end
        ]

        mission_key = (
            f"optimizer-{facility_id}-"
            f"{window_start.strftime('%Y%m%d%H%M')}-"
            f"{window_end.strftime('%Y%m%d%H%M')}"
        )

        return {
            "mission_id":
                mission_key,
            "facility_id":
                facility_id,
            "facility_name":
                facility_name,
            "severity":
                severity,
            "category":
                "Coordinated Recovery",
            "title": (
                f"Recover {recovered} of {before_misses} projected SLA misses"
                if before_misses
                else (
                    f"Protect {len(rows)} at-risk appointments"
                )
            ),
            "objective": (
                f"Coordinate {len(rows)} at-risk appointments at {facility_name} "
                "against actual shift labor, available forklift equipment, "
                "temperature-compatible docks and existing mission reservations."
            ),
            "status":
                "Proposed",
            "priority_score":
                priority_score,
            "impacted_appointment_count":
                len(rows),
            "appointments_at_risk":
                len(rows),
            "appointment_ids": [
                item["appt_id"]
                for item in plan
            ],
            "primary_appointment_id":
                primary["appt_id"]
                if primary
                else None,
            "projected_minutes_saved":
                round(
                    minutes_saved,
                    1,
                ),
            "estimated_financial_benefit":
                round(
                    net_savings,
                    2,
                ),
            "recovery_probability":
                recovery_probability,
            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "recommended_actions":
                recommended_actions,
            "source_alert_ids":
                [],
            "window_start":
                window_start.isoformat(),
            "window_end":
                window_end.isoformat(),
            "projected_sla_misses_before":
                before_misses,
            "projected_sla_misses_after":
                after_misses,
            "appointments_recovered":
                recovered,
            "resource_capacity": {
                "source":
                    "labor_shifts + equipment + committed missions",
                "available_forklift_equipment":
                    max(
                        (
                            values[
                                "forklift_capacity"
                            ]
                            for values
                            in resource_snapshot.values()
                        ),
                        default=0,
                    ),
                "hourly":
                    capacity_by_hour,
            },
            "scenario_constraints": {
                "max_extra_loaders_per_hour":
                    max_extra_loaders_per_hour,
                "max_extra_forklifts_per_hour":
                    max_extra_forklifts_per_hour,
                "max_staging_labor_per_hour":
                    max_staging_labor_per_hour,
                "allow_dock_reassignment":
                    allow_dock_reassignment,
            },
            "dock_feasibility": {
                "active_docks":
                    len(docks),
                "dock_moves":
                    sum(
                        1
                        for item in plan
                        if any(
                            action[
                                "action_code"
                            ]
                            == "REASSIGN_DOCK"
                            for action
                            in item["actions"]
                        )
                    ),
                "temperature_compatibility_enforced":
                    True,
            },
            "learning": {
                "profiles_available":
                    len(effectiveness_profiles),
                "appointments_using_learned_effects":
                    sum(
                        1
                        for item in plan
                        if item["learning_evidence"][
                            "source"
                        ]
                        == "realized_outcome_learning"
                    ),
                "method":
                    "contextual realized-outcome blending",
            },
            "resource_shortages":
                resource_shortages[:10],
            "appointment_plan":
                plan,
            "optimizer_version":
                OPTIMIZER_VERSION,
        }


    @staticmethod
    def _enrich_candidate(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        predicted_delay = max(
            0.0,
            float(result.get("predicted_delay_minutes") or 0),
        )
        predicted_duration = max(
            0.0,
            float(result.get("predicted_duration_minutes") or 0),
        )
        baseline_turn = predicted_delay + predicted_duration
        sla_minutes = float(result.get("sla_minutes") or 120)
        detention_rate = float(result.get("detention_cost_per_hour") or 0)
        result["baseline_turn_minutes"] = baseline_turn
        result["minutes_over_sla"] = max(0.0, baseline_turn - sla_minutes)
        result["baseline_exposure"] = (
            result["minutes_over_sla"] / 60.0 * detention_rate
        )
        result["complex_load"] = (
            int(result.get("pallet_count") or 0) >= 24
            or int(result.get("sku_count") or 0) >= 8
        )
        return result

    @staticmethod
    def _option_evaluation(
        row: dict[str, Any],
        option: InterventionOption,
        learned_estimate: dict[str, Any] | None = None,
    ) -> tuple[Any, ...]:
        baseline_turn = float(
            row["baseline_turn_minutes"]
        )
        sla_minutes = float(
            row["sla_minutes"]
        )
        detention_rate = float(
            row["detention_cost_per_hour"]
            or 0
        )
        baseline_exposure = float(
            row["baseline_exposure"]
        )

        effective_minutes_saved = float(
            (
                learned_estimate
                or {}
            ).get(
                "minutes_saved",
                option.minutes_saved,
            )
        )
        projected_turn = max(
            30.0,
            baseline_turn
            - effective_minutes_saved,
        )
        recovered = (
            projected_turn
            <= sla_minutes
        )
        projected_exposure = (
            max(
                0.0,
                projected_turn
                - sla_minutes,
            )
            / 60.0
            * detention_rate
        )
        net_value = (
            baseline_exposure
            - projected_exposure
            - option.action_cost
        )
        resource_units = (
            option.extra_loaders
            + option.extra_forklifts
            + option.staging_labor
        )
        return (
            int(recovered),
            (
                -resource_units
                if recovered
                else option.minutes_saved
            ),
            net_value,
            (
                float(
                    (
                        learned_estimate
                        or {}
                    ).get(
                        "avg_realized_net_savings"
                    )
                    or 0
                )
            ),
            effective_minutes_saved,
            -option.action_cost,
        )

    @staticmethod
    def _choose_option(
        row: dict[str, Any],
        *,
        available_loaders: int,
        available_forklifts: int,
        effectiveness_profiles: dict[
            tuple[str, str, str, str, str, str],
            dict[str, Any],
        ] | None = None,
    ) -> InterventionOption:
        viable: list[InterventionOption] = []
        for option in OPTIONS:
            loader_need = option.extra_loaders + option.staging_labor
            if loader_need > available_loaders:
                continue
            if option.extra_forklifts > available_forklifts:
                continue
            if (
                "PRE_STAGE_PRODUCTS" in option.action_codes
                and not bool(row["complex_load"])
            ):
                continue
            viable.append(option)

        if not viable:
            return OPTIONS[0]

        return max(
            viable,
            key=lambda option:
                MultiAppointmentOptimizerService._option_evaluation(
                    row,
                    option,
                    learned_estimate=
                        MultiAppointmentOptimizerService._learned_option_estimate(
                            row,
                            option,
                            effectiveness_profiles,
                        ),
                ),
        )

    @staticmethod
    def _actions_for_option(
        row: dict[str, Any],
        option: InterventionOption,
        minutes_saved: float,
    ) -> list[dict[str, Any]]:
        if not option.action_codes:
            return []

        per_action_minutes = (
            minutes_saved / len(option.action_codes)
            if option.action_codes
            else 0.0
        )
        per_action_cost = (
            option.action_cost / len(option.action_codes)
            if option.action_codes
            else 0.0
        )

        descriptions = {
            "ADD_LOADER": "Add one loader during the appointment service window.",
            "ADD_FORKLIFT": "Reserve one additional forklift for the appointment service window.",
            "PRE_STAGE_PRODUCTS": "Pre-stage the highest-handling products before dock service begins.",
        }
        actions: list[dict[str, Any]] = []
        for code in option.action_codes:
            actions.append(
                {
                    "action_code": code,
                    "action_description": descriptions[code],
                    "additional_loaders": 1 if code == "ADD_LOADER" else 0,
                    "additional_forklifts": 1 if code == "ADD_FORKLIFT" else 0,
                    "staging_labor": 1 if code == "PRE_STAGE_PRODUCTS" else 0,
                    "required_dock_id": row.get("assigned_dock_id"),
                    "expected_minutes_saved": round(per_action_minutes, 1),
                    "estimated_action_cost": round(per_action_cost, 2),
                }
            )
        return actions

    @staticmethod
    def _summary_action(item: dict[str, Any]) -> str:
        action_names = {
            "ADD_LOADER": "+1 loader",
            "ADD_FORKLIFT": "+1 forklift",
            "PRE_STAGE_PRODUCTS": "pre-stage products",
            "REASSIGN_DOCK": "move dock",
        }
        labels = [
            action_names.get(action["action_code"], action["action_code"])
            for action in item["actions"]
        ]
        dock = item.get("dock_name") or item.get("dock_id") or "current dock"
        return (
            f"{item['appt_id']} · {dock}: {', '.join(labels)} · "
            f"{item['baseline_projected_turn_minutes']:.0f}→"
            f"{item['optimized_projected_turn_minutes']:.0f} min"
        )

    @staticmethod
    def _resolve_window(
        date_from: date | datetime | None,
        date_to: date | datetime | None,
    ) -> tuple[datetime, datetime]:
        today = datetime.now().date()

        if isinstance(date_from, datetime):
            start = date_from
        elif isinstance(date_from, date):
            start = datetime.combine(date_from, time.min)
        else:
            start = datetime.combine(today, time.min)

        if isinstance(date_to, datetime):
            end = date_to
        elif isinstance(date_to, date):
            end = datetime.combine(date_to, time.min)
        else:
            end = start + timedelta(days=1)

        if end <= start:
            end = start + timedelta(days=1)
        return start, end
