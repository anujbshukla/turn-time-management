from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


OPTIMIZER_VERSION = "multi-appointment-v1.0"


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
        row = self.db.execute(
            text(
                """
                UPDATE optimization_missions
                SET status = :status
                WHERE mission_id = :mission_id
                RETURNING
                    mission_id,
                    facility_id,
                    status,
                    optimizer_version,
                    created_at;
                """
            ),
            {
                "mission_id": mission_id,
                "status": status,
            },
        ).mappings().one_or_none()
        if row is None:
            raise ValueError(
                f"Optimization mission {mission_id} does not exist."
            )

        self.db.execute(
            text(
                """
                UPDATE optimization_mission_actions
                SET status = :status
                WHERE mission_id = :mission_id;
                """
            ),
            {
                "mission_id": mission_id,
                "status": status,
            },
        )
        self.db.commit()
        return dict(row)

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
                    profile.base_forklift_capacity

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

    def _load_hourly_usage(
        self,
        facility_id: str,
        window_start: datetime,
        window_end: datetime,
    ) -> dict[datetime, dict[str, int]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    date_trunc('hour', appointment.scheduled_time) AS hour_bucket,
                    COALESCE(
                        SUM(
                            allocation.planned_loaders
                            + allocation.planned_staging_labor
                        ),
                        0
                    )::INTEGER AS loaders_used,
                    COALESCE(
                        SUM(allocation.planned_forklifts),
                        0
                    )::INTEGER AS forklifts_used
                FROM appointments appointment
                JOIN appointment_resource_allocations allocation
                  ON allocation.appt_id = appointment.appt_id
                WHERE appointment.appt_id LIKE 'DEMO%'
                  AND appointment.facility_id = :facility_id
                  AND appointment.status NOT IN ('Completed', 'Cancelled')
                  AND appointment.scheduled_time >= :window_start
                  AND appointment.scheduled_time < :window_end
                GROUP BY date_trunc('hour', appointment.scheduled_time);
                """
            ),
            {
                "facility_id": facility_id,
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().all()
        return {
            row["hour_bucket"]: {
                "loaders_used": int(row["loaders_used"] or 0),
                "forklifts_used": int(row["forklifts_used"] or 0),
            }
            for row in rows
        }

    def _optimize_facility(
        self,
        facility_id: str,
        rows: list[dict[str, Any]],
        window_start: datetime,
        window_end: datetime,
    ) -> dict[str, Any] | None:
        if not rows:
            return None

        loader_capacity = int(rows[0]["base_loader_capacity"] or 1)
        forklift_capacity = int(rows[0]["base_forklift_capacity"] or 1)
        usage = self._load_hourly_usage(
            facility_id,
            window_start,
            window_end,
        )

        headroom: dict[datetime, dict[str, int]] = {}
        for bucket, used in usage.items():
            headroom[bucket] = {
                "loaders": max(
                    0,
                    loader_capacity - used["loaders_used"],
                ),
                "forklifts": max(
                    0,
                    forklift_capacity - used["forklifts_used"],
                ),
            }

        enriched = [self._enrich_candidate(row) for row in rows]
        enriched.sort(
            key=lambda row: (
                not bool(row["predicted_missed"]),
                -float(row["minutes_over_sla"]),
                -float(row["turn_risk_score"]),
                -float(row["baseline_exposure"]),
                row["scheduled_time"],
            )
        )

        plan: list[dict[str, Any]] = []
        for priority_order, row in enumerate(enriched, start=1):
            bucket = row["scheduled_time"].replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            available = headroom.setdefault(
                bucket,
                {
                    "loaders": loader_capacity,
                    "forklifts": forklift_capacity,
                },
            )

            option = self._choose_option(
                row,
                available_loaders=available["loaders"],
                available_forklifts=available["forklifts"],
            )

            available["loaders"] -= (
                option.extra_loaders + option.staging_labor
            )
            available["forklifts"] -= option.extra_forklifts

            optimized_turn = max(
                30.0,
                float(row["baseline_turn_minutes"])
                - option.minutes_saved,
            )
            optimized_turn = min(
                float(row["baseline_turn_minutes"]),
                optimized_turn,
            )
            minutes_saved = max(
                0.0,
                float(row["baseline_turn_minutes"])
                - optimized_turn,
            )
            sla_recovered = optimized_turn <= float(row["sla_minutes"])

            detention_rate = float(row["detention_cost_per_hour"] or 0)
            optimized_exposure = (
                max(0.0, optimized_turn - float(row["sla_minutes"]))
                / 60.0
                * detention_rate
            )
            gross_savings = max(
                0.0,
                float(row["baseline_exposure"]) - optimized_exposure,
            )
            net_savings = gross_savings - option.action_cost

            actions = self._actions_for_option(
                row,
                option,
                minutes_saved,
            )

            plan.append(
                {
                    "appt_id": row["appt_id"],
                    "scheduled_time": row["scheduled_time"].isoformat(),
                    "dock_id": row.get("assigned_dock_id"),
                    "dock_name": row.get("dock_name"),
                    "baseline_risk_score": int(row["turn_risk_score"] or 0),
                    "baseline_sla_miss_probability": round(
                        float(row["sla_miss_probability"] or 0),
                        4,
                    ),
                    "baseline_projected_turn_minutes": round(
                        float(row["baseline_turn_minutes"]),
                        1,
                    ),
                    "optimized_projected_turn_minutes": round(
                        optimized_turn,
                        1,
                    ),
                    "minutes_saved": round(minutes_saved, 1),
                    "sla_minutes": int(row["sla_minutes"]),
                    "sla_recovered": bool(sla_recovered),
                    "priority_order": priority_order,
                    "baseline_exposure": round(float(row["baseline_exposure"]), 2),
                    "optimized_exposure": round(optimized_exposure, 2),
                    "gross_savings": round(gross_savings, 2),
                    "action_cost": round(option.action_cost, 2),
                    "net_savings": round(net_savings, 2),
                    "actions": actions,
                }
            )

        before_misses = sum(
            1
            for row in enriched
            if bool(row["predicted_missed"])
            or float(row["baseline_turn_minutes"]) > float(row["sla_minutes"])
        )
        after_misses = sum(1 for item in plan if not item["sla_recovered"])
        recovered = max(0, before_misses - after_misses)
        minutes_saved = sum(float(item["minutes_saved"]) for item in plan)
        net_savings = sum(float(item["net_savings"]) for item in plan)

        facility_name = str(rows[0].get("facility_name") or facility_id)
        primary = plan[0] if plan else None
        actionable = [item for item in plan if item["actions"]]

        recommended_actions = [
            self._summary_action(item)
            for item in actionable[:5]
        ]
        if not recommended_actions:
            recommended_actions = [
                "Keep the current plan; available recovery capacity does not improve the SLA outcome."
            ]

        recovery_probability = (
            round(recovered / before_misses * 100, 1)
            if before_misses > 0
            else 100.0
        )

        priority_score = min(
            100,
            max(
                int(float(row["turn_risk_score"] or 0))
                for row in rows
            )
            + min(15, before_misses * 2),
        )
        severity = (
            "Critical"
            if before_misses >= 3
            or priority_score >= 90
            else "High"
            if before_misses > 0
            else "Warning"
        )

        mission_key = (
            f"optimizer-{facility_id}-"
            f"{window_start.strftime('%Y%m%d%H%M')}-"
            f"{window_end.strftime('%Y%m%d%H%M')}"
        )

        return {
            "mission_id": mission_key,
            "facility_id": facility_id,
            "facility_name": facility_name,
            "severity": severity,
            "category": "Coordinated Recovery",
            "title": (
                f"Recover {recovered} of {before_misses} projected SLA misses"
                if before_misses
                else f"Protect {len(rows)} at-risk appointments"
            ),
            "objective": (
                f"Coordinate {len(rows)} at-risk appointments at {facility_name} "
                "as one recovery problem, allocating loaders, forklifts and staging "
                "capacity without double-booking resources."
            ),
            "status": "Proposed",
            "priority_score": priority_score,
            "impacted_appointment_count": len(rows),
            "appointments_at_risk": len(rows),
            "appointment_ids": [item["appt_id"] for item in plan],
            "primary_appointment_id": primary["appt_id"] if primary else None,
            "projected_minutes_saved": round(minutes_saved, 1),
            "estimated_financial_benefit": round(net_savings, 2),
            "recovery_probability": recovery_probability,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "recommended_actions": recommended_actions,
            "source_alert_ids": [],
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "projected_sla_misses_before": before_misses,
            "projected_sla_misses_after": after_misses,
            "appointments_recovered": recovered,
            "resource_capacity": {
                "base_loader_capacity": loader_capacity,
                "base_forklift_capacity": forklift_capacity,
            },
            "appointment_plan": plan,
            "optimizer_version": OPTIMIZER_VERSION,
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
    def _choose_option(
        row: dict[str, Any],
        *,
        available_loaders: int,
        available_forklifts: int,
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

        baseline_turn = float(row["baseline_turn_minutes"])
        sla_minutes = float(row["sla_minutes"])
        detention_rate = float(row["detention_cost_per_hour"] or 0)
        baseline_exposure = float(row["baseline_exposure"])

        def evaluation(option: InterventionOption) -> tuple[Any, ...]:
            projected_turn = max(30.0, baseline_turn - option.minutes_saved)
            recovered = projected_turn <= sla_minutes
            projected_exposure = (
                max(0.0, projected_turn - sla_minutes)
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
            # Recovery first; then protect scarce resources and financial value.
            return (
                int(recovered),
                -resource_units if recovered else option.minutes_saved,
                net_value,
                option.minutes_saved,
                -option.action_cost,
            )

        return max(viable, key=evaluation)

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
