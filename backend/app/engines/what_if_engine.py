from __future__ import annotations

from typing import Any


class WhatIfEngine:
    """
    Simulates operational recovery changes without
    modifying the database.
    """

    EXTRA_LOADER_MINUTES_SAVED = 12
    EXTRA_FORKLIFT_MINUTES_SAVED = 9
    PRE_STAGE_MINUTES_SAVED = 15

    EXTRA_LOADER_COST = 50.00
    EXTRA_FORKLIFT_COST = 35.00
    PRE_STAGE_COST = 20.00

    def simulate(
        self,
        *,
        appointment: dict[str, Any],
        prediction: dict[str, Any] | None,
        actions: list[dict[str, Any]],
        selected_action_ids: list[int],
        extra_loaders: int = 0,
        extra_forklifts: int = 0,
        pre_stage_products: bool = False,
    ) -> dict[str, Any]:
        if prediction is None:
            raise ValueError(
                "A prediction is required to run "
                "What-If analysis."
            )

        selected_action_id_set = set(
            selected_action_ids
        )

        available_action_ids = {
            action["recommendation_action_id"]
            for action in actions
        }

        invalid_action_ids = (
            selected_action_id_set
            - available_action_ids
        )

        if invalid_action_ids:
            invalid_list = sorted(
                invalid_action_ids
            )

            raise ValueError(
                "The following recovery actions do not "
                f"belong to this appointment: {invalid_list}"
            )

        predicted_delay = max(
            0,
            prediction.get(
                "predicted_delay_minutes",
                0,
            )
            or 0,
        )

        predicted_duration = (
            prediction.get(
                "predicted_duration_minutes",
                0,
            )
            or 0
        )

        baseline_turn_time = (
            predicted_delay
            + predicted_duration
        )

        sla_minutes = (
            appointment.get("sla_minutes")
            or 120
        )

        detention_cost_per_hour = float(
            appointment.get(
                "detention_cost_per_hour",
                0,
            )
            or 0
        )

        baseline_miss_probability = float(
            prediction.get(
                "sla_miss_probability",
                0,
            )
            or 0
        )

        baseline_risk_score = float(
            prediction.get(
                "turn_risk_score",
                0,
            )
            or 0
        )

        selected_actions = [
            action
            for action in actions
            if action[
                "recommendation_action_id"
            ] in selected_action_id_set
        ]

        action_minutes_saved = sum(
            float(
                action.get(
                    "estimated_minutes_saved",
                    0,
                )
                or 0
            )
            for action in selected_actions
        )

        selected_action_cost = sum(
            float(
                action.get(
                    "estimated_action_cost",
                    0,
                )
                or 0
            )
            for action in selected_actions
        )

        manual_minutes_saved = (
            extra_loaders
            * self.EXTRA_LOADER_MINUTES_SAVED
            + extra_forklifts
            * self.EXTRA_FORKLIFT_MINUTES_SAVED
            + (
                self.PRE_STAGE_MINUTES_SAVED
                if pre_stage_products
                else 0
            )
        )

        manual_action_cost = (
            extra_loaders
            * self.EXTRA_LOADER_COST
            + extra_forklifts
            * self.EXTRA_FORKLIFT_COST
            + (
                self.PRE_STAGE_COST
                if pre_stage_products
                else 0
            )
        )

        total_minutes_saved = (
            action_minutes_saved
            + manual_minutes_saved
        )

        # Avoid unrealistic reductions below a basic
        # operational floor.
        operational_floor = max(
            30,
            round(predicted_duration * 0.35),
        )

        projected_turn_time = max(
            operational_floor,
            baseline_turn_time
            - total_minutes_saved,
        )

        actual_minutes_saved = max(
            0,
            baseline_turn_time
            - projected_turn_time,
        )

        improvement_ratio = (
            actual_minutes_saved
            / baseline_turn_time
            if baseline_turn_time > 0
            else 0
        )

        projected_miss_probability = max(
            0.02,
            min(
                0.99,
                baseline_miss_probability
                - improvement_ratio * 0.90,
            ),
        )

        if projected_turn_time <= sla_minutes:
            projected_miss_probability = min(
                projected_miss_probability,
                0.25,
            )

        projected_recovery_probability = (
            1 - projected_miss_probability
        )

        projected_risk_score = max(
            0,
            min(
                100,
                baseline_risk_score
                - improvement_ratio * 85,
            ),
        )

        baseline_excess_minutes = max(
            0,
            baseline_turn_time - sla_minutes,
        )

        projected_excess_minutes = max(
            0,
            projected_turn_time - sla_minutes,
        )

        baseline_detention_exposure = (
            baseline_excess_minutes
            / 60
            * detention_cost_per_hour
        )

        projected_detention_exposure = (
            projected_excess_minutes
            / 60
            * detention_cost_per_hour
        )

        gross_savings = max(
            0,
            baseline_detention_exposure
            - projected_detention_exposure,
        )

        total_action_cost = (
            selected_action_cost
            + manual_action_cost
        )

        net_savings = (
            gross_savings
            - total_action_cost
        )

        return {
            "baseline": {
                "predicted_turn_time_minutes":
                    round(
                        baseline_turn_time,
                        1,
                    ),
                "sla_minutes":
                    sla_minutes,
                "sla_miss_probability":
                    round(
                        baseline_miss_probability,
                        4,
                    ),
                "turn_risk_score":
                    round(
                        baseline_risk_score,
                        1,
                    ),
                "detention_exposure":
                    round(
                        baseline_detention_exposure,
                        2,
                    ),
            },
            "scenario": {
                "projected_turn_time_minutes":
                    round(
                        projected_turn_time,
                        1,
                    ),
                "minutes_saved":
                    round(
                        actual_minutes_saved,
                        1,
                    ),
                "sla_recovered":
                    projected_turn_time
                    <= sla_minutes,
                "projected_sla_miss_probability":
                    round(
                        projected_miss_probability,
                        4,
                    ),
                "projected_recovery_probability":
                    round(
                        projected_recovery_probability,
                        4,
                    ),
                "projected_risk_score":
                    round(
                        projected_risk_score,
                        1,
                    ),
                "action_cost":
                    round(
                        total_action_cost,
                        2,
                    ),
                "projected_detention_exposure":
                    round(
                        projected_detention_exposure,
                        2,
                    ),
                "gross_savings":
                    round(
                        gross_savings,
                        2,
                    ),
                "net_savings":
                    round(
                        net_savings,
                        2,
                    ),
            },
        }