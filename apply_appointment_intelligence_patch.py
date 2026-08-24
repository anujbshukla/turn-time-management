from pathlib import Path

ROOT = Path.cwd()
repo = ROOT / "backend/app/repositories/appointment_repository.py"
drawer = ROOT / "frontend/src/components/AppointmentDetailsDrawer.tsx"
css = ROOT / "frontend/src/App.css"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Patch anchor not found: {label}")
    return text.replace(old, new, 1)

# Backend repository
text = repo.read_text(encoding="utf-8")
text = replace_once(text,
    "from app.repositories.outcome_rules import outcome_filter_sql\n",
    "from app.repositories.outcome_rules import outcome_filter_sql\nfrom app.services.appointment_explainability import (\n    build_action_rationale,\n    build_risk_contributors,\n    build_sla_outcome_reason,\n)\n",
    "backend import")
text = replace_once(text,
    "                    a.trailer_number,\n\n                    a.pallet_count,",
    "                    a.trailer_number,\n                    driver.driver_name,\n                    driver.license_number,\n                    driver.license_state,\n                    driver.phone_number AS driver_phone,\n                    driver.tractor_number,\n                    a.origin_name,\n                    a.origin_city,\n                    a.origin_state,\n                    a.destination_name,\n                    a.destination_city,\n                    a.destination_state,\n\n                    a.pallet_count,",
    "appointment select fields")
text = replace_once(text,
    "                LEFT JOIN customers customer\n                    ON customer.customer_id =\n                        a.customer_id\n\n                WHERE a.appt_id = :appt_id;",
    "                LEFT JOIN customers customer\n                    ON customer.customer_id =\n                        a.customer_id\n\n                LEFT JOIN appointment_drivers driver\n                    ON driver.appt_id = a.appt_id\n\n                WHERE a.appt_id = :appt_id;",
    "driver join")
text = replace_once(text,
    "            actions = [\n                dict(row)\n                for row in action_rows\n            ]",
    "            actions = [dict(row) for row in action_rows]\n            for action in actions:\n                action[\"recommendation_reason\"] = build_action_rationale(\n                    action, appointment_dict, prediction_dict\n                )",
    "action rationale")
text = replace_once(text,
    "        sla_variance_minutes = (\n            actual_turn_time - sla_minutes\n            if actual_turn_time is not None\n            else None\n        )\n\n        return {",
    "        sla_variance_minutes = (\n            actual_turn_time - sla_minutes\n            if actual_turn_time is not None\n            else None\n        )\n\n        risk_contributors = build_risk_contributors(appointment_dict, prediction_dict)\n        sla_outcome_status, sla_outcome_reason = build_sla_outcome_reason(\n            appointment_dict,\n            recommendation_used=recommendation_used,\n            accepted_minutes_saved=accepted_minutes_saved,\n            actual_sla_met=actual_sla_met,\n            actual_sla_missed=actual_sla_missed,\n            was_late=was_late,\n            sla_variance_minutes=sla_variance_minutes,\n        )\n\n        return {",
    "explanation calculation")
text = replace_once(text,
    "                \"sla_variance_minutes\": sla_variance_minutes,\n\n                \"sla_minutes\":",
    "                \"sla_variance_minutes\": sla_variance_minutes,\n                \"sla_outcome_status\": sla_outcome_status,\n                \"sla_outcome_reason\": sla_outcome_reason,\n                \"risk_contributors\": risk_contributors,\n\n                \"sla_minutes\":",
    "recovery summary explainability")
repo.write_text(text, encoding="utf-8", newline="\n")

# Drawer
text = drawer.read_text(encoding="utf-8")
text = replace_once(text,
    'import { AppointmentCopilot } from "./AppointmentCopilot";\n',
    'import { AppointmentCopilot } from "./AppointmentCopilot";\nimport { AppointmentOperationalIntelligence } from "./AppointmentOperationalIntelligence";\n',
    "drawer import")
text = replace_once(text,
    '                                <div className="details-grid">',
    '                                {appointment && recovery && (\n                                    <AppointmentOperationalIntelligence\n                                        appointment={appointment}\n                                        prediction={prediction}\n                                        products={details.products}\n                                        recovery={recovery}\n                                    />\n                                )}\n\n                                <div className="details-grid">',
    "operational intelligence insertion")
text = replace_once(text,
    "                                                        <p>\n                                                            {\n                                                                action\n                                                                    .action_description\n                                                            }\n                                                        </p>\n",
    "                                                        <p>\n                                                            {action.action_description}\n                                                        </p>\n\n                                                        {action.recommendation_reason && (\n                                                            <p className=\"action-recommendation-reason\">\n                                                                <strong>Why recommended: </strong>\n                                                                {action.recommendation_reason}\n                                                            </p>\n                                                        )}\n",
    "action reason insertion")
drawer.write_text(text, encoding="utf-8", newline="\n")

# CSS append
css_text = css.read_text(encoding="utf-8")
patch = (ROOT / "frontend_intelligence.css").read_text(encoding="utf-8")
marker = "/* Appointment operational intelligence */"
if marker not in css_text:
    css.write_text(css_text.rstrip() + "\n\n" + patch.strip() + "\n", encoding="utf-8", newline="\n")

print("Appointment intelligence patch applied successfully.")
