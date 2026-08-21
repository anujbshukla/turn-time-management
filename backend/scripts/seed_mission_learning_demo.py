from __future__ import annotations

"""
Persistent demo foundation for mission execution + action-effectiveness learning.

Run from backend:
    python scripts/seed_mission_learning_demo.py

Properties:
- Uses existing Completed appointments as the operational grounding.
- Creates exactly 50 completed historical missions per facility (500 total
  when the 10 demo facilities are available).
- One executed recovery action per mission so realized action attribution is
  unambiguous for this demo-learning foundation.
- Outcomes are deterministic and reproducible; they include wins, partial
  recoveries and misses.
- Rebuilds optimization_action_effectiveness FROM the generated mission/action
  outcomes rather than hand-writing ranking rows.
- Idempotent: only rows tagged with optimizer_version=demo-learning-v1 are
  replaced on rerun.
"""

from dataclasses import dataclass
from datetime import timedelta
import hashlib
from typing import Any

from sqlalchemy import inspect, text

from app.database import get_db


SEED_VERSION = "demo-learning-v1"
MISSIONS_PER_FACILITY = 50

ACTION_SPECS = (
    {
        "code": "REASSIGN_DOCK",
        "description": "Reassign to a lower-congestion feasible dock.",
        "base_minutes": 24.0,
        "base_success": 0.82,
        "loaders": 0,
        "forklifts": 0,
        "staging": 0,
    },
    {
        "code": "PRE_STAGE_PRODUCTS",
        "description": "Pre-stage appointment products in loading sequence.",
        "base_minutes": 20.0,
        "base_success": 0.78,
        "loaders": 0,
        "forklifts": 0,
        "staging": 1,
    },
    {
        "code": "ADD_LOADER",
        "description": "Assign one additional loader for the constrained handling window.",
        "base_minutes": 17.0,
        "base_success": 0.72,
        "loaders": 1,
        "forklifts": 0,
        "staging": 0,
    },
    {
        "code": "PRIORITY_SEQUENCE",
        "description": "Move the appointment forward in the executable loading sequence.",
        "base_minutes": 14.0,
        "base_success": 0.68,
        "loaders": 0,
        "forklifts": 0,
        "staging": 0,
    },
    {
        "code": "ADD_FORKLIFT",
        "description": "Assign one additional forklift during the handling window.",
        "base_minutes": 12.0,
        "base_success": 0.63,
        "loaders": 0,
        "forklifts": 1,
        "staging": 0,
    },
)


@dataclass
class Outcome:
    facility_id: str
    appt_id: str
    appointment_type: str
    load_type: str
    temperature_zone: str
    pallet_band: str
    congestion_band: str
    action_signature: str
    realized_minutes_saved: float
    realized_net_savings: float
    sla_success: bool


def stable_fraction(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16**12 - 1)


def table_columns(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def pallet_band(value: Any) -> str:
    pallets = int(value or 0)
    if pallets >= 30:
        return "30+"
    if pallets >= 20:
        return "20-29"
    if pallets >= 10:
        return "10-19"
    return "0-9"


def congestion_band(value: Any) -> str:
    congestion = float(value or 0)
    if congestion >= 80:
        return "80+"
    if congestion >= 60:
        return "60-79"
    if congestion >= 40:
        return "40-59"
    return "0-39"


def insert_dynamic(db, table: str, values: dict[str, Any], allowed: set[str]) -> int:
    payload = {key: value for key, value in values.items() if key in allowed}
    columns = ", ".join(payload)
    binds = ", ".join(f":{key}" for key in payload)
    returning = " RETURNING mission_id" if table == "optimization_missions" else ""
    result = db.execute(
        text(f"INSERT INTO {table} ({columns}) VALUES ({binds}){returning}"),
        payload,
    )
    if table == "optimization_missions":
        return int(result.scalar_one())
    return 0


def main() -> None:
    db_gen = get_db()
    db = next(db_gen)
    try:
        inspector = inspect(db.bind)
        mission_cols = table_columns(inspector, "optimization_missions")
        action_cols = table_columns(inspector, "optimization_mission_actions")
        profile_cols = table_columns(inspector, "optimization_action_effectiveness")
        appointment_cols = table_columns(inspector, "appointments")

        required_mission = {
            "mission_id", "facility_id", "window_start", "window_end", "status",
            "appointments_at_risk", "projected_sla_misses_before",
            "projected_sla_misses_after", "estimated_net_savings",
            "optimizer_version", "created_at",
        }
        required_action = {
            "mission_action_id", "mission_id", "appt_id", "sequence_number",
            "action_code", "action_description", "additional_loaders",
            "additional_forklifts", "staging_labor", "required_dock_id",
            "expected_minutes_saved",
        }
        required_profile = {
            "facility_id", "action_signature", "appointment_type", "load_type",
            "temperature_zone", "pallet_band", "congestion_band", "sample_size",
            "sla_success_rate", "avg_realized_minutes_saved",
        }

        if not required_mission.issubset(mission_cols):
            raise RuntimeError(
                "optimization_missions schema is missing required columns: "
                + ", ".join(sorted(required_mission - mission_cols))
            )
        if not required_action.issubset(action_cols):
            raise RuntimeError(
                "optimization_mission_actions schema is missing required columns: "
                + ", ".join(sorted(required_action - action_cols))
            )
        if not required_profile.issubset(profile_cols):
            raise RuntimeError(
                "optimization_action_effectiveness schema is missing required columns: "
                + ", ".join(sorted(required_profile - profile_cols))
            )

        # Idempotency: remove only this demo foundation's prior mission rows.
        prior_ids = [
            int(row[0])
            for row in db.execute(
                text(
                    "SELECT mission_id FROM optimization_missions "
                    "WHERE optimizer_version = :version"
                ),
                {"version": SEED_VERSION},
            ).all()
        ]
        if prior_ids:
            db.execute(
                text(
                    "DELETE FROM optimization_mission_actions "
                    "WHERE mission_id = ANY(:mission_ids)"
                ),
                {"mission_ids": prior_ids},
            )
            db.execute(
                text(
                    "DELETE FROM optimization_missions "
                    "WHERE mission_id = ANY(:mission_ids)"
                ),
                {"mission_ids": prior_ids},
            )

        # Profiles are recomputed from this foundation. Since the user's current
        # database has zero missions/profiles, this is the clean deterministic
        # demo-learning baseline. Do not run this seed in a production database.
        db.execute(text("DELETE FROM optimization_action_effectiveness"))

        facilities = [
            str(row[0])
            for row in db.execute(
                text(
                    """
                    SELECT facility_id
                    FROM appointments
                    WHERE status = 'Completed'
                    GROUP BY facility_id
                    HAVING COUNT(*) >= :minimum
                    ORDER BY facility_id
                    """
                ),
                {"minimum": MISSIONS_PER_FACILITY},
            ).all()
        ]
        if not facilities:
            raise RuntimeError("No facility has enough completed appointments.")

        temp_select = (
            "COALESCE(a.temperature_zone, 'Ambient') AS temperature_zone"
            if "temperature_zone" in appointment_cols
            else "'Ambient'::VARCHAR AS temperature_zone"
        )

        allocation_tables = set(inspector.get_table_names())
        allocation_cols = (
            table_columns(inspector, "appointment_resource_allocations")
            if "appointment_resource_allocations" in allocation_tables
            else set()
        )
        if "dock_congestion_percent" in allocation_cols:
            congestion_select = (
                "COALESCE(allocation.dock_congestion_percent, 0) "
                "AS dock_congestion_percent"
            )
            allocation_join = (
                "LEFT JOIN appointment_resource_allocations allocation "
                "ON allocation.appt_id = a.appt_id"
            )
        else:
            congestion_select = "0::NUMERIC AS dock_congestion_percent"
            allocation_join = ""

        outcomes: list[Outcome] = []
        mission_count = 0

        for facility_id in facilities:
            # Hash ordering gives a stable cross-section across the one-year
            # history without depending on database RANDOM().
            rows = db.execute(
                text(
                    f"""
                    SELECT
                        a.appt_id,
                        a.facility_id,
                        a.scheduled_time,
                        COALESCE(a.appointment_type, 'Unknown') AS appointment_type,
                        COALESCE(a.load_type, 'Unknown') AS load_type,
                        {temp_select},
                        COALESCE(a.pallet_count, 0) AS pallet_count,
                        COALESCE(a.actual_turn_time_minutes, a.sla_minutes, 60)
                            AS actual_turn_time_minutes,
                        COALESCE(a.sla_minutes, 120) AS sla_minutes,
                        COALESCE(a.detention_cost_per_hour, 100)
                            AS detention_cost_per_hour,
                        a.assigned_dock_id,
                        {congestion_select}
                    FROM appointments a
                    {allocation_join}
                    WHERE a.status = 'Completed'
                      AND a.facility_id = :facility_id
                    ORDER BY md5(a.appt_id || :version)
                    LIMIT :limit
                    """
                ),
                {
                    "facility_id": facility_id,
                    "version": SEED_VERSION,
                    "limit": MISSIONS_PER_FACILITY,
                },
            ).mappings().all()

            for index, row in enumerate(rows):
                spec = ACTION_SPECS[index % len(ACTION_SPECS)]
                jitter = stable_fraction(
                    f"{SEED_VERSION}|{row['appt_id']}|{spec['code']}"
                )
                workload = min(10.0, float(row["pallet_count"] or 0) / 6.0)
                congestion = float(row["dock_congestion_percent"] or 0)

                # Different actions respond to different contexts.
                context_bonus = 0.0
                if spec["code"] == "REASSIGN_DOCK":
                    context_bonus += max(0.0, congestion - 45.0) / 12.0
                elif spec["code"] == "PRE_STAGE_PRODUCTS":
                    context_bonus += workload * 0.45
                elif spec["code"] == "ADD_LOADER":
                    context_bonus += workload * 0.35
                elif spec["code"] == "ADD_FORKLIFT":
                    context_bonus += workload * 0.20

                realized_minutes = max(
                    1.0,
                    round(
                        spec["base_minutes"]
                        + context_bonus
                        + (jitter - 0.5) * 12.0,
                        1,
                    ),
                )

                success_threshold = spec["base_success"]
                # Severe congestion and very large loads make recovery harder.
                success_threshold -= max(0.0, congestion - 75.0) / 250.0
                success_threshold -= max(
                    0.0, float(row["pallet_count"] or 0) - 35.0
                ) / 250.0
                success_threshold = min(0.92, max(0.40, success_threshold))
                sla_success = stable_fraction(
                    f"success|{row['appt_id']}|{spec['code']}"
                ) < success_threshold

                detention_rate = float(row["detention_cost_per_hour"] or 100)
                realized_savings = round(
                    realized_minutes / 60.0 * detention_rate
                    * (1.0 if sla_success else 0.45),
                    2,
                )
                estimated_savings = round(
                    spec["base_minutes"] / 60.0 * detention_rate,
                    2,
                )

                scheduled = row["scheduled_time"]
                created_at = scheduled - timedelta(minutes=75)
                window_start = scheduled - timedelta(minutes=60)
                window_end = scheduled + timedelta(minutes=120)
                completed_at = scheduled + timedelta(
                    minutes=float(row["actual_turn_time_minutes"] or 60)
                )

                mission_values = {
                    "facility_id": row["facility_id"],
                    "window_start": window_start,
                    "window_end": window_end,
                    "status": "Completed",
                    "appointments_at_risk": 1,
                    "projected_sla_misses_before": 1,
                    "projected_sla_misses_after": 0 if sla_success else 1,
                    "estimated_net_savings": estimated_savings,
                    "optimizer_version": SEED_VERSION,
                    "created_at": created_at,
                    # Optional execution/outcome columns from later migrations.
                    "accepted_at": created_at + timedelta(minutes=5),
                    "started_at": created_at + timedelta(minutes=10),
                    "completed_at": completed_at,
                    "realized_minutes_saved": realized_minutes,
                    "realized_net_savings": realized_savings,
                    "realized_sla_misses_after": 0 if sla_success else 1,
                    "realized_sla_recovered": sla_success,
                    "execution_notes": "Synthetic historical demo-learning outcome.",
                }
                mission_id = insert_dynamic(
                    db,
                    "optimization_missions",
                    mission_values,
                    mission_cols,
                )

                action_values = {
                    "mission_id": mission_id,
                    "appt_id": row["appt_id"],
                    "sequence_number": 1,
                    "action_code": spec["code"],
                    "action_description": spec["description"],
                    "additional_loaders": spec["loaders"],
                    "additional_forklifts": spec["forklifts"],
                    "staging_labor": spec["staging"],
                    "required_dock_id": (
                        row["assigned_dock_id"]
                        if spec["code"] == "REASSIGN_DOCK"
                        else None
                    ),
                    "expected_minutes_saved": spec["base_minutes"],
                    # Optional later execution columns.
                    "status": "Completed",
                    "execution_status": "Completed",
                    "accepted_at": created_at + timedelta(minutes=5),
                    "started_at": created_at + timedelta(minutes=10),
                    "completed_at": completed_at,
                    "realized_minutes_saved": realized_minutes,
                    "realized_net_savings": realized_savings,
                    "actual_minutes_saved": realized_minutes,
                }
                insert_dynamic(
                    db,
                    "optimization_mission_actions",
                    action_values,
                    action_cols,
                )

                outcomes.append(
                    Outcome(
                        facility_id=str(row["facility_id"]),
                        appt_id=str(row["appt_id"]),
                        appointment_type=str(row["appointment_type"]),
                        load_type=str(row["load_type"]),
                        temperature_zone=str(row["temperature_zone"]),
                        pallet_band=pallet_band(row["pallet_count"]),
                        congestion_band=congestion_band(
                            row["dock_congestion_percent"]
                        ),
                        action_signature=spec["code"],
                        realized_minutes_saved=realized_minutes,
                        realized_net_savings=realized_savings,
                        sla_success=sla_success,
                    )
                )
                mission_count += 1

        # ------------------------------------------------------------------
        # Learning rebuild: derive profiles from realized mission outcomes.
        # ------------------------------------------------------------------
        grouped: dict[tuple[str, ...], list[Outcome]] = {}
        for outcome in outcomes:
            key = (
                outcome.facility_id,
                outcome.action_signature,
                outcome.appointment_type,
                outcome.load_type,
                outcome.temperature_zone,
                outcome.pallet_band,
                outcome.congestion_band,
            )
            grouped.setdefault(key, []).append(outcome)

        for key, samples in grouped.items():
            (
                facility_id,
                signature,
                appointment_type,
                load_type,
                temperature_zone,
                p_band,
                c_band,
            ) = key
            sample_size = len(samples)
            sla_success_rate = sum(
                1 for item in samples if item.sla_success
            ) / sample_size
            avg_minutes = sum(
                item.realized_minutes_saved for item in samples
            ) / sample_size
            avg_savings = sum(
                item.realized_net_savings for item in samples
            ) / sample_size

            profile_values = {
                "facility_id": facility_id,
                "action_signature": signature,
                "appointment_type": appointment_type,
                "load_type": load_type,
                "temperature_zone": temperature_zone,
                "pallet_band": p_band,
                "congestion_band": c_band,
                "sample_size": sample_size,
                "sla_success_rate": round(sla_success_rate, 6),
                "avg_realized_minutes_saved": round(avg_minutes, 3),
                "avg_realized_net_savings": round(avg_savings, 2),
                "confidence_weight": round(min(1.0, sample_size / 10.0), 6),
                "last_outcome_at": max(
                    row["scheduled_time"]
                    for row in db.execute(
                        text(
                            """
                            SELECT scheduled_time
                            FROM appointments
                            WHERE appt_id = ANY(:appt_ids)
                            """
                        ),
                        {"appt_ids": [item.appt_id for item in samples]},
                    ).mappings().all()
                ),
                "updated_at": max(
                    row["scheduled_time"]
                    for row in db.execute(
                        text(
                            """
                            SELECT scheduled_time
                            FROM appointments
                            WHERE appt_id = ANY(:appt_ids)
                            """
                        ),
                        {"appt_ids": [item.appt_id for item in samples]},
                    ).mappings().all()
                ),
            }
            insert_dynamic(
                db,
                "optimization_action_effectiveness",
                profile_values,
                profile_cols,
            )

        db.commit()

        profile_count = int(
            db.execute(
                text("SELECT COUNT(*) FROM optimization_action_effectiveness")
            ).scalar_one()
        )
        fac001_missions = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM optimization_missions
                    WHERE optimizer_version = :version
                      AND facility_id = 'FAC001'
                    """
                ),
                {"version": SEED_VERSION},
            ).scalar_one()
        )

        print("Mission Learning Demo Foundation created.")
        print(f"Facilities: {len(facilities)}")
        print(f"Completed missions created: {mission_count}")
        print(f"FAC001 missions: {fac001_missions}")
        print(f"Learned effectiveness profiles: {profile_count}")
        print(f"Optimizer version: {SEED_VERSION}")

        leaderboard = db.execute(
            text(
                """
                SELECT
                    action_signature,
                    SUM(sample_size)::INTEGER AS samples,
                    ROUND(
                        SUM(avg_realized_minutes_saved * sample_size)
                        / NULLIF(SUM(sample_size), 0),
                        1
                    ) AS avg_minutes_saved,
                    ROUND(
                        SUM(sla_success_rate * sample_size)
                        / NULLIF(SUM(sample_size), 0) * 100,
                        1
                    ) AS sla_success_percent
                FROM optimization_action_effectiveness
                WHERE facility_id = 'FAC001'
                GROUP BY action_signature
                ORDER BY avg_minutes_saved DESC, samples DESC
                """
            )
        ).mappings().all()

        print("\nFAC001 learned action leaderboard:")
        for row in leaderboard:
            print(
                f"  {row['action_signature']}: "
                f"{row['avg_minutes_saved']} min saved | "
                f"{row['sla_success_percent']}% SLA success | "
                f"{row['samples']} samples"
            )

    except Exception:
        db.rollback()
        raise
    finally:
        try:
            db_gen.close()
        except Exception:
            db.close()


if __name__ == "__main__":
    main()
