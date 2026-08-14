from __future__ import annotations


def recommendation_used_exists_sql(
    appointment_alias: str,
) -> str:
    """Return the canonical SQL predicate for an accepted recommendation.

    An appointment is recommendation-assisted when either its parent
    recommendation is Accepted/Completed or at least one child recovery action
    is explicitly Accepted.
    """

    return f"""
        EXISTS (
            SELECT 1

            FROM appointment_recommendations
                AS outcome_recommendation

            WHERE outcome_recommendation.appt_id =
                  {appointment_alias}.appt_id

              AND (
                  outcome_recommendation.status IN (
                      'Accepted',
                      'Completed'
                  )

                  OR EXISTS (
                      SELECT 1

                      FROM recommendation_actions
                          AS outcome_action

                      WHERE
                          outcome_action.recommendation_id =
                          outcome_recommendation.recommendation_id

                        AND
                          outcome_action.decision_status =
                          'Accepted'
                  )
              )
        )
    """.strip()


def completed_sla_met_sql(
    appointment_alias: str,
) -> str:
    """Canonical completed-SLA-success predicate."""

    return f"""
        {appointment_alias}.status = 'Completed'
        AND {appointment_alias}.actual_turn_time_minutes IS NOT NULL
        AND {appointment_alias}.actual_turn_time_minutes <=
            {appointment_alias}.sla_minutes
    """.strip()


def completed_sla_missed_sql(
    appointment_alias: str,
) -> str:
    """Canonical completed-SLA-miss predicate.

    Actual turn time is authoritative. The legacy flag is used only when an
    older completed record has no actual turn-time value.
    """

    return f"""
        {appointment_alias}.status = 'Completed'
        AND (
            {appointment_alias}.actual_turn_time_minutes >
                {appointment_alias}.sla_minutes

            OR (
                {appointment_alias}.actual_turn_time_minutes IS NULL
                AND {appointment_alias}.actual_sla_missed = TRUE
            )
        )
    """.strip()


def outcome_filter_sql(
    appointment_alias: str,
) -> str:
    """Return the shared paginated-table outcome filter."""

    recommendation_used = recommendation_used_exists_sql(
        appointment_alias,
    )
    sla_met = completed_sla_met_sql(
        appointment_alias,
    )
    sla_missed = completed_sla_missed_sql(
        appointment_alias,
    )

    return f"""
        AND (
            CAST(:outcome AS VARCHAR) IS NULL

            OR (
                CAST(:outcome AS VARCHAR) =
                    'Recovered with recommendations'

                AND {appointment_alias}.actual_arrival_delay_minutes > 0

                AND ({sla_met})

                AND ({recommendation_used})
            )

            OR (
                CAST(:outcome AS VARCHAR) =
                    'Recovered without recommendations'

                AND {appointment_alias}.actual_arrival_delay_minutes > 0

                AND ({sla_met})

                AND NOT ({recommendation_used})
            )

            OR (
                CAST(:outcome AS VARCHAR) = 'Missed SLA'

                AND {appointment_alias}.actual_arrival_delay_minutes > 0

                AND ({sla_missed})
            )
        )
    """.strip()
