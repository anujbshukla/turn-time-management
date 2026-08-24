from __future__ import annotations

from typing import Any


def build_risk_contributors(appointment: dict[str, Any], prediction: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return transparent operational risk contributors.

    These are explanatory contributors derived from the same operational facts
    available to the appointment experience; they are intentionally labelled
    as contributors rather than model/SHAP attribution values.
    """
    if prediction is None:
        return []

    contributors: list[dict[str, Any]] = []
    delay = int(appointment.get("actual_arrival_delay_minutes") or prediction.get("predicted_delay_minutes") or 0)
    pallets = int(appointment.get("pallet_count") or 0)
    skus = int(appointment.get("sku_count") or 0)
    traffic = int(appointment.get("traffic_severity") or 0)
    weather = int(appointment.get("weather_severity") or 0)
    duration = int(prediction.get("predicted_duration_minutes") or 0)
    sla = int(appointment.get("sla_minutes") or 120)

    if delay > 0:
        contributors.append({"label": "Arrival delay", "impact_points": min(24, max(6, round(delay * 0.55))), "reason": f"Arrival is {delay} minutes behind the appointment plan."})
    if duration >= max(45, round(sla * 0.45)):
        contributors.append({"label": "Service duration", "impact_points": min(18, max(6, round(duration / 6))), "reason": f"Predicted handling time is {duration} minutes against a {sla}-minute SLA."})
    if pallets >= 25:
        contributors.append({"label": "Load volume", "impact_points": min(14, 6 + (pallets - 25) // 4), "reason": f"The load contains {pallets} pallets, increasing handling effort."})
    if skus >= 7:
        contributors.append({"label": "SKU complexity", "impact_points": min(10, 4 + (skus - 7) // 2), "reason": f"{skus} SKUs increase staging and verification complexity."})
    if traffic >= 3:
        contributors.append({"label": "Traffic", "impact_points": min(10, traffic * 2), "reason": f"Traffic severity is {traffic}/5."})
    if weather >= 3:
        contributors.append({"label": "Weather", "impact_points": min(10, weather * 2), "reason": f"Weather severity is {weather}/5."})
    if appointment.get("surge_indicator"):
        contributors.append({"label": "Warehouse surge", "impact_points": 10, "reason": "The facility is operating under surge-volume conditions."})
    if not appointment.get("assigned_dock_id"):
        contributors.append({"label": "Dock readiness", "impact_points": 8, "reason": "No dock is currently assigned to the appointment."})

    if not contributors:
        contributors.append({"label": "Baseline operating risk", "impact_points": max(1, round(float(prediction.get("sla_miss_probability") or 0) * 100)), "reason": "No single dominant operational exception is present; risk reflects the combined appointment profile."})

    contributors.sort(key=lambda item: item["impact_points"], reverse=True)
    return contributors[:6]


def build_sla_outcome_reason(
    appointment: dict[str, Any],
    *,
    recommendation_used: bool,
    accepted_minutes_saved: float,
    actual_sla_met: bool,
    actual_sla_missed: bool,
    was_late: bool,
    sla_variance_minutes: float | None,
) -> tuple[str, str]:
    if appointment.get("status") != "Completed":
        return "In progress", "The SLA outcome is still open. The live SLA clock and current risk contributors show the remaining recovery window."

    variance = float(sla_variance_minutes or 0)
    arrival_delay = int(appointment.get("actual_arrival_delay_minutes") or 0)
    actual_service = appointment.get("actual_loading_duration_minutes")

    if actual_sla_missed:
        causes: list[str] = []
        if arrival_delay > 0:
            causes.append(f"arrival was {arrival_delay} minutes late")
        if actual_service is not None:
            causes.append(f"load/unload activity took {int(actual_service)} minutes")
        if appointment.get("surge_indicator"):
            causes.append("the facility was operating under surge conditions")
        detail = ", and ".join(causes) if causes else "the realized turn exceeded the SLA window"
        return "SLA Missed", f"The appointment exceeded SLA by {abs(round(variance))} minutes because {detail}."

    if actual_sla_met and was_late:
        recovery_detail = (
            f"Accepted recovery actions were expected to save about {round(accepted_minutes_saved)} minutes and helped offset the late arrival."
            if recommendation_used and accepted_minutes_saved > 0
            else "Operational execution recovered the late arrival without a recorded accepted recovery action."
        )
        return "SLA Recovered", f"The appointment arrived {arrival_delay} minutes late but completed {abs(round(variance))} minutes inside SLA. {recovery_detail}"

    if actual_sla_met:
        return "SLA Met", f"The appointment completed {abs(round(variance))} minutes inside the SLA window with no recovery from a late arrival required."

    return "Completed", "The appointment is completed, but the available operational timestamps are insufficient to determine a reliable SLA explanation."


def build_action_rationale(action: dict[str, Any], appointment: dict[str, Any], prediction: dict[str, Any] | None) -> str:
    title = str(action.get("action_title") or action.get("action_code") or "This action").lower()
    saved = int(action.get("estimated_minutes_saved") or 0)
    reasons: list[str] = []

    delay = int(appointment.get("actual_arrival_delay_minutes") or (prediction or {}).get("predicted_delay_minutes") or 0)
    if delay > 0:
        reasons.append(f"the appointment has a {delay}-minute arrival delay")
    if appointment.get("surge_indicator"):
        reasons.append("the facility is under surge-volume pressure")
    if int(appointment.get("pallet_count") or 0) >= 25:
        reasons.append(f"the {appointment.get('pallet_count')}-pallet load has elevated handling demand")

    if "dock" in title or action.get("required_dock_id"):
        dock = action.get("required_dock_id") or "an alternate dock"
        reasons.insert(0, f"{dock} can reduce waiting or improve dock compatibility")
    if "labor" in title or "loader" in title or int(action.get("additional_loaders") or 0) > 0:
        reasons.insert(0, "additional labor can compress service time during the remaining SLA window")
    if "forklift" in title or int(action.get("additional_forklifts") or 0) > 0:
        reasons.insert(0, "additional material-handling capacity can reduce loading/unloading cycle time")
    if "stage" in title:
        reasons.insert(0, "pre-staging reduces non-value-added searching and staging time")
    if not reasons:
        reasons.append("it is the highest-value feasible action identified for the current appointment state")

    impact = f" It is estimated to save about {saved} minutes." if saved > 0 else ""
    return "Recommended because " + "; ".join(reasons[:3]) + "." + impact
