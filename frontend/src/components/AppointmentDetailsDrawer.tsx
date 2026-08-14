import { useEffect, useState } from "react";
import { EditAppointmentDrawer } from "./EditAppointmentDrawer";
import { useWhatIf } from "../hooks/useWhatIf";
import {
    updateRecommendationDecisions,
} from "../services/recommendations";
import {
    AppointmentCopilot,
} from "./AppointmentCopilot";
import type {
    ActionDecisionStatus,
} from "../services/recommendations";

import type {
    AppointmentDetailsResponse,
    RecommendationAction,
} from "../types/appointmentDetails";

import type {
    AppointmentListItem,
} from "../types/appointments";


type AppointmentDetailsDrawerProps = {
    selectedAppointment: AppointmentListItem | null;
    details: AppointmentDetailsResponse | null;
    loading: boolean;
    error: string | null;
    onRefresh: () => void;
    onClose: () => void;
};


function formatDate(
    value: string | null | undefined,
) {
    if (!value) {
        return "—";
    }

    return new Date(value).toLocaleString([], {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}


function formatPercent(
    value: number | null | undefined,
) {
    if (value == null) {
        return "—";
    }

    return `${Math.round(value * 100)}%`;
}


function formatCurrency(
    value: number | null | undefined,
) {
    return `$${(value ?? 0).toLocaleString(
        "en-US",
        {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        },
    )}`;
}

function formatEventType(
    eventType: string,
): string {
    const labels: Record<string, string> = {
        APPOINTMENT_CREATED:
            "Appointment created",

        APPOINTMENT_UPDATED:
            "Appointment updated",

        SCHEDULED:
            "Appointment scheduled",

        ETA_UPDATED:
            "Carrier ETA updated",

        CARRIER_DELAYED:
            "Carrier delay detected",

        ARRIVED:
            "Carrier arrived",

        CHECKED_IN:
            "Carrier checked in",

        DOCK_ASSIGNED:
            "Dock assigned",

        LOADING_STARTED:
            "Loading started",

        LOADING_COMPLETED:
            "Loading completed",

        UNLOADING_STARTED:
            "Unloading started",

        UNLOADING_COMPLETED:
            "Unloading completed",

        DEPARTED:
            "Carrier departed",

        PREDICTION_GENERATED:
            "AI prediction generated",

        RECOMMENDATION_GENERATED:
            "AI recovery plan generated",

        RECOVERY_ACTION_ACCEPTED:
            "Recovery action accepted",

        RECOVERY_ACTION_REJECTED:
            "Recovery action rejected",

        RECOVERY_ACTION_RESET:
            "Recovery action reset to pending",
    };

    return (
        labels[eventType] ??
        eventType
            .replaceAll("_", " ")
            .toLowerCase()
            .replace(
                /^./,
                (firstCharacter) =>
                    firstCharacter.toUpperCase(),
            )
    );
}

function riskLevel(score: number) {
    if (score >= 80) {
        return "critical";
    }

    if (score >= 60) {
        return "high";
    }

    if (score >= 30) {
        return "medium";
    }

    return "low";
}


function actionResourceSummary(
    action: RecommendationAction,
) {
    const resources: string[] = [];

    if (action.additional_loaders > 0) {
        resources.push(
            `${action.additional_loaders} loader${action.additional_loaders === 1
                ? ""
                : "s"
            }`,
        );
    }

    if (action.additional_forklifts > 0) {
        resources.push(
            `${action.additional_forklifts} forklift${action.additional_forklifts === 1
                ? ""
                : "s"
            }`,
        );
    }

    if (action.required_equipment_type) {
        resources.push(
            action.required_equipment_type,
        );
    }

    if (action.required_dock_id) {
        resources.push(
            action.required_dock_id,
        );
    }

    return resources.length > 0
        ? resources.join(" · ")
        : "No additional resources";
}


export function AppointmentDetailsDrawer({
    selectedAppointment,
    details,
    loading,
    error,
    onRefresh,
    onClose,
}: AppointmentDetailsDrawerProps) {
    const [editOpen, setEditOpen] = useState(false);

    const [
        selectedActionIds,
        setSelectedActionIds,
    ] = useState<Set<number>>(
        () => new Set<number>(),
    );

    const [
        savingDecision,
        setSavingDecision,
    ] = useState(false);

    const [
        decisionError,
        setDecisionError,
    ] = useState<string | null>(null);

    const [
        extraLoaders,
        setExtraLoaders,
    ] = useState(0);

    const [
        extraForklifts,
        setExtraForklifts,
    ] = useState(0);

    const [
        preStageProducts,
        setPreStageProducts,
    ] = useState(false);

    useEffect(() => {
        setSelectedActionIds(
            new Set<number>(),
        );

        setDecisionError(null);

        setExtraLoaders(0);

        setExtraForklifts(0);

        setPreStageProducts(false);
    }, [
        details?.recommendation
            ?.recommendation_id,
    ]);

    const {
        simulation: whatIfSimulation,
        loading: whatIfLoading,
        error: whatIfError,
    } = useWhatIf({
        appointmentId:
            selectedAppointment?.appt_id,

        selectedActionIds:
            Array.from(selectedActionIds),

        extraLoaders,

        extraForklifts,

        preStageProducts,

        enabled:
            Boolean(
                selectedAppointment &&
                details?.prediction,
            ),
    });
    const selectedWhatIfActions =
        details?.recommendation_actions.filter(
            (action) =>
                selectedActionIds.has(
                    action.recommendation_action_id,
                ),
        ) ?? [];

    const highestImpactAction =
        selectedWhatIfActions.reduce<
            RecommendationAction | null
        >(
            (highest, action) => {
                if (
                    highest === null ||
                    action.estimated_minutes_saved >
                    highest.estimated_minutes_saved
                ) {
                    return action;
                }

                return highest;
            },
            null,
        );

    const manualContributors = [
        {
            label: "Additional loaders",
            minutesSaved: extraLoaders * 12,
        },
        {
            label: "Additional forklifts",
            minutesSaved: extraForklifts * 9,
        },
        {
            label: "Pre-stage products",
            minutesSaved:
                preStageProducts ? 15 : 0,
        },
    ];

    const topManualContributor =
        manualContributors.reduce<{
            label: string;
            minutesSaved: number;
        } | null>(
            (highest, contributor) => {
                if (
                    contributor.minutesSaved <= 0
                ) {
                    return highest;
                }

                if (
                    highest === null ||
                    contributor.minutesSaved >
                    highest.minutesSaved
                ) {
                    return contributor;
                }

                return highest;
            },
            null,
        );

    const topContributor =
        highestImpactAction &&
            (
                !topManualContributor ||
                highestImpactAction
                    .estimated_minutes_saved >=
                topManualContributor.minutesSaved
            )
            ? {
                label:
                    highestImpactAction.action_title,
                minutesSaved:
                    highestImpactAction
                        .estimated_minutes_saved,
            }
            : topManualContributor;

    const simulationConfidence =
        whatIfSimulation
            ? Math.min(
                98,
                Math.max(
                    65,
                    Math.round(
                        72 +
                        whatIfSimulation
                            .selected_action_ids
                            .length *
                        3 +
                        (preStageProducts ? 3 : 0) +
                        Math.min(
                            8,
                            extraLoaders * 2 +
                            extraForklifts * 2,
                        ),
                    ),
                ),
            )
            : null;

    const confidenceLabel =
        simulationConfidence == null
            ? "Unavailable"
            : simulationConfidence >= 90
                ? "High confidence"
                : simulationConfidence >= 75
                    ? "Moderate confidence"
                    : "Directional estimate";
    function toggleActionSelection(
        actionId: number,
    ) {
        setSelectedActionIds((current) => {
            const next = new Set(current);

            if (next.has(actionId)) {
                next.delete(actionId);
            } else {
                next.add(actionId);
            }

            return next;
        });
    }


    function selectAllActions() {
        if (!details) {
            return;
        }

        setSelectedActionIds(
            new Set(
                details.recommendation_actions.map(
                    (action) =>
                        action.recommendation_action_id,
                ),
            ),
        );
    }


    function clearActionSelection() {
        setSelectedActionIds(
            new Set<number>(),
        );
    }


    async function applyDecision(
        decisionStatus: ActionDecisionStatus,
    ) {
        if (
            !details?.recommendation ||
            selectedActionIds.size === 0
        ) {
            return;
        }

        setSavingDecision(true);
        setDecisionError(null);

        try {
            const selectedActions =
                details.recommendation_actions
                    .filter((action) =>
                        selectedActionIds.has(
                            action.recommendation_action_id,
                        ),
                    )
                    .map((action) => ({
                        recommendation_action_id:
                            action.recommendation_action_id,
                        decision_status: decisionStatus,
                    }));

            await updateRecommendationDecisions(
                details.recommendation
                    .recommendation_id,
                {
                    decided_by:
                        "Warehouse Supervisor",
                    actions: selectedActions,
                },
            );

            setSelectedActionIds(
                new Set<number>(),
            );

            onRefresh();
        } catch (saveError) {
            setDecisionError(
                saveError instanceof Error
                    ? saveError.message
                    : "Unable to update recovery actions",
            );
        } finally {
            setSavingDecision(false);
        }
    }


    if (!selectedAppointment) {
        return null;
    }


    const appointment =
        details?.appointment;

    const prediction =
        details?.prediction;

    const recommendation =
        details?.recommendation;

    const recovery =
        details?.recovery_summary;

    const acceptedActions =
        details?.recommendation_actions.filter(
            (action) =>
                action.decision_status === "Accepted",
        ) ?? [];

    const isCompleted =
        recovery?.is_completed ??
        appointment?.status === "Completed";

    const score =
        prediction?.turn_risk_score ??
        selectedAppointment.turn_risk_score ??
        0;

    const actionCount =
        details?.recommendation_actions
            .length ?? 0;

    const allActionsSelected =
        actionCount > 0 &&
        selectedActionIds.size === actionCount;


    return (
        <>
            <button
                type="button"
                className="drawer-backdrop"
                aria-label="Close appointment details"
                onClick={onClose}
            />

            <aside
                className="appointment-drawer"
                aria-label="Appointment decision center"
            >
                <div className="drawer-header">
                    <div>
                        <span className="drawer-eyebrow">
                            AI Decision Center
                        </span>

                        <h2>
                            {selectedAppointment.appt_id}
                        </h2>

                        <p>
                            {appointment?.customer_name ??
                                selectedAppointment.customer_name ??
                                "Unknown customer"}
                        </p>
                    </div>

                    <div className="drawer-header-actions">
                        {details && appointment?.status !== "Completed" && (
                            <button type="button" className="secondary-button drawer-edit-button" onClick={() => setEditOpen(true)}>
                                Edit appointment
                            </button>
                        )}
                        <button
                        type="button"
                        className="drawer-close"
                        onClick={onClose}
                        aria-label="Close"
                    >
                        ×
                    </button>
                    </div>
                </div>

                <div className="drawer-content">
                    {loading && (
                        <section className="drawer-section">
                            Loading appointment intelligence...
                        </section>
                    )}

                    {error && (
                        <section className="drawer-section table-error">
                            {error}
                        </section>
                    )}

                    {!loading && details && (
                        <>
                            <section className="drawer-section">
                                <div className="drawer-section-heading">
                                    <div>
                                        <span className="drawer-section-label">
                                            Operational snapshot
                                        </span>

                                        <h3>
                                            Current appointment state
                                        </h3>
                                    </div>

                                    <span
                                        className={`risk-badge ${riskLevel(
                                            score,
                                        )}`}
                                    >
                                        {score} risk
                                    </span>
                                </div>

                                <div className="details-grid">
                                    <div>
                                        <span>Status</span>
                                        <strong>
                                            {appointment?.status ??
                                                "—"}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>Priority</span>
                                        <strong>
                                            {appointment?.priority_tier ??
                                                appointment?.priority ??
                                                "—"}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>Facility</span>
                                        <strong>
                                            {appointment?.facility_name ??
                                                "—"}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>Dock</span>
                                        <strong>
                                            {appointment?.dock_name ??
                                                appointment
                                                    ?.assigned_dock_id ??
                                                "Unassigned"}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>Carrier</span>
                                        <strong>
                                            {appointment?.carrier_name ??
                                                "—"}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>Trailer</span>
                                        <strong>
                                            {appointment?.trailer_number ??
                                                "—"}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>Pallets</span>
                                        <strong>
                                            {appointment?.pallet_count ??
                                                0}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>SKUs</span>
                                        <strong>
                                            {appointment?.sku_count ??
                                                0}
                                        </strong>
                                    </div>
                                </div>
                            </section>


                            {isCompleted && (
                                <section className="drawer-section completed-outcome-section">
                                    <div className="drawer-section-heading">
                                        <div>
                                            <span className="drawer-section-label">
                                                Completed outcome
                                            </span>

                                            <h3>
                                                {recovery?.completed_outcome ??
                                                    "Completed appointment"}
                                            </h3>
                                        </div>

                                        <span
                                            className={`completed-outcome-badge ${
                                                recovery?.actual_sla_missed
                                                    ? "missed"
                                                    : "recovered"
                                            }`}
                                        >
                                            {recovery?.actual_sla_missed
                                                ? "SLA missed"
                                                : "SLA met"}
                                        </span>
                                    </div>

                                    <div className="completed-outcome-metrics">
                                        <div>
                                            <span>Actual turn</span>
                                            <strong>
                                                {recovery
                                                    ?.actual_turn_time_minutes ??
                                                    appointment
                                                        ?.actual_turn_time_minutes ??
                                                    "—"}
                                                <small> min</small>
                                            </strong>
                                        </div>

                                        <div>
                                            <span>Target SLA</span>
                                            <strong>
                                                {recovery?.sla_minutes ??
                                                    appointment?.sla_minutes ??
                                                    "—"}
                                                <small> min</small>
                                            </strong>
                                        </div>

                                        <div>
                                            <span>SLA variance</span>
                                            <strong
                                                className={
                                                    (recovery
                                                        ?.sla_variance_minutes ??
                                                        0) > 0
                                                        ? "negative-impact"
                                                        : "positive-impact"
                                                }
                                            >
                                                {recovery
                                                    ?.sla_variance_minutes ==
                                                null
                                                    ? "—"
                                                    : `${
                                                        recovery
                                                            .sla_variance_minutes >
                                                        0
                                                            ? "+"
                                                            : ""
                                                    }${recovery.sla_variance_minutes}`}
                                                {recovery
                                                    ?.sla_variance_minutes !=
                                                    null && (
                                                    <small> min</small>
                                                )}
                                            </strong>
                                        </div>

                                        <div>
                                            <span>Accepted actions</span>
                                            <strong>
                                                {acceptedActions.length}
                                            </strong>
                                        </div>
                                    </div>

                                    <div className="accepted-outcome-actions">
                                        <div className="accepted-outcome-actions-heading">
                                            <strong>
                                                Accepted recovery recommendations
                                            </strong>

                                            <span>
                                                {recovery?.recommendation_used
                                                    ? recovery.actual_sla_met
                                                        ? "Contributed to a recovered SLA"
                                                        : "Applied, but SLA was still missed"
                                                    : "No recovery recommendation was accepted"}
                                            </span>
                                        </div>

                                        {acceptedActions.length > 0 ? (
                                            <div className="accepted-outcome-action-list">
                                                {acceptedActions.map(
                                                    (action) => (
                                                        <article
                                                            key={
                                                                action
                                                                    .recommendation_action_id
                                                            }
                                                            className="accepted-outcome-action"
                                                        >
                                                            <div>
                                                                <strong>
                                                                    {action.action_title}
                                                                </strong>

                                                                <span>
                                                                    {action.action_description}
                                                                </span>
                                                            </div>

                                                            <div className="accepted-outcome-action-meta">
                                                                <strong>
                                                                    {action.estimated_minutes_saved}
                                                                    {" "}
                                                                    min
                                                                </strong>

                                                                <span>
                                                                    {action.decision_by ??
                                                                        "Warehouse Supervisor"}
                                                                </span>
                                                            </div>
                                                        </article>
                                                    ),
                                                )}
                                            </div>
                                        ) : (
                                            <p className="accepted-outcome-empty">
                                                This completed appointment has no
                                                accepted recovery actions.
                                            </p>
                                        )}
                                    </div>
                                </section>
                            )}

                            <section className="drawer-section risk-assessment-section">
                                <span className="drawer-section-label">
                                    AI risk assessment
                                </span>

                                <div className="risk-assessment-grid">
                                    <div>
                                        <span>Risk score</span>

                                        <strong>
                                            {score}
                                            <small>/100</small>
                                        </strong>
                                    </div>

                                    <div>
                                        <span>
                                            SLA miss probability
                                        </span>

                                        <strong>
                                            {formatPercent(
                                                prediction
                                                    ?.sla_miss_probability,
                                            )}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>
                                            {isCompleted
                                                ? "Original predicted turn"
                                                : "Predicted turn"}
                                        </span>

                                        <strong>
                                            {recovery
                                                ?.predicted_turn_time_minutes ??
                                                "—"}
                                            <small> min</small>
                                        </strong>
                                    </div>

                                    <div>
                                        <span>Target SLA</span>

                                        <strong>
                                            {recovery?.sla_minutes ??
                                                appointment?.sla_minutes ??
                                                "—"}
                                            <small> min</small>
                                        </strong>
                                    </div>
                                </div>

                                <div className="comparison-grid">
                                    <div className="comparison-card">
                                        <span>
                                            {isCompleted
                                                ? "Original forecast without recovery"
                                                : "Without recovery plan"}
                                        </span>

                                        <strong>
                                            {recovery
                                                ?.predicted_turn_time_minutes ??
                                                "—"}{" "}
                                            min
                                        </strong>

                                        <small>
                                            {prediction?.predicted_missed
                                                ? "SLA miss predicted"
                                                : "SLA currently achievable"}
                                        </small>
                                    </div>

                                    <div className="comparison-card recovered">
                                        <span>
                                            Full AI recovery plan
                                        </span>

                                        <strong>
                                            {recovery
                                                ?.proposed_projected_turn_time_minutes ??
                                                recovery
                                                    ?.projected_turn_time_minutes ??
                                                "—"}{" "}
                                            min
                                        </strong>

                                        <small>
                                            {(
                                                recovery
                                                    ?.proposed_sla_recovered ??
                                                recovery?.sla_recovered ??
                                                false
                                            )
                                                ? "SLA recovered"
                                                : "Further action required"}
                                        </small>
                                    </div>
                                </div>

                                <div className="comparison-grid">
                                    <div className="comparison-card">
                                        <span>
                                            Currently accepted actions
                                        </span>

                                        <strong>
                                            {recovery
                                                ?.accepted_projected_turn_time_minutes ??
                                                recovery
                                                    ?.predicted_turn_time_minutes ??
                                                "—"}{" "}
                                            min
                                        </strong>

                                        <small>
                                            {recovery
                                                ?.accepted_sla_recovered
                                                ? "Accepted actions recover SLA"
                                                : "Additional actions may be required"}
                                        </small>
                                    </div>

                                    <div className="comparison-card recovered">
                                        <span>
                                            Accepted minutes saved
                                        </span>

                                        <strong>
                                            {recovery
                                                ?.accepted_minutes_saved ??
                                                0}{" "}
                                            min
                                        </strong>

                                        <small>
                                            Based only on accepted actions
                                        </small>
                                    </div>
                                </div>
                            </section>


                            <section className="drawer-section">
                                <span className="drawer-section-label">
                                    Root causes
                                </span>

                                <h3>
                                    Why this appointment is at risk
                                </h3>

                                <ul className="root-cause-list">
                                    {(appointment
                                        ?.actual_arrival_delay_minutes ??
                                        prediction
                                            ?.predicted_delay_minutes ??
                                        0) > 0 && (
                                            <li>
                                                Carrier is expected or
                                                recorded{" "}
                                                <strong>
                                                    {appointment
                                                        ?.actual_arrival_delay_minutes ??
                                                        prediction
                                                            ?.predicted_delay_minutes}{" "}
                                                    minutes late
                                                </strong>
                                                .
                                            </li>
                                        )}

                                    {(appointment?.pallet_count ??
                                        0) >= 25 && (
                                            <li>
                                                High load volume of{" "}
                                                <strong>
                                                    {appointment?.pallet_count}{" "}
                                                    pallets
                                                </strong>{" "}
                                                increases handling time.
                                            </li>
                                        )}

                                    {(appointment?.sku_count ??
                                        0) >= 7 && (
                                            <li>
                                                The appointment contains{" "}
                                                <strong>
                                                    {appointment?.sku_count}{" "}
                                                    SKUs
                                                </strong>
                                                , increasing staging and
                                                verification effort.
                                            </li>
                                        )}

                                    {(appointment
                                        ?.traffic_severity ??
                                        0) >= 3 && (
                                            <li>
                                                Traffic conditions are
                                                elevated at{" "}
                                                <strong>
                                                    severity{" "}
                                                    {
                                                        appointment
                                                            ?.traffic_severity
                                                    }
                                                </strong>
                                                .
                                            </li>
                                        )}

                                    {(appointment
                                        ?.weather_severity ??
                                        0) >= 3 && (
                                            <li>
                                                Weather conditions may
                                                affect arrival and handling
                                                operations.
                                            </li>
                                        )}

                                    {appointment
                                        ?.surge_indicator && (
                                            <li>
                                                The facility is operating
                                                under a surge-volume
                                                condition.
                                            </li>
                                        )}
                                </ul>
                            </section>


                            <section className="drawer-section">
                                <div className="drawer-section-heading">
                                    <div>
                                        <span className="drawer-section-label">
                                            AI recovery plan
                                        </span>

                                        <h3>
                                            Warehouse actions
                                        </h3>
                                    </div>

                                    <div className="minutes-saved">
                                        <strong>
                                            {recovery
                                                ?.proposed_minutes_saved ??
                                                recovery
                                                    ?.total_minutes_saved ??
                                                0}
                                        </strong>

                                        <span>
                                            proposed minutes saved
                                        </span>
                                    </div>
                                </div>

                                {actionCount > 0 && (
                                    <div className="drawer-selection-toolbar">
                                        <span>
                                            {selectedActionIds.size} of{" "}
                                            {actionCount} selected
                                        </span>

                                        <button
                                            type="button"
                                            onClick={
                                                allActionsSelected
                                                    ? clearActionSelection
                                                    : selectAllActions
                                            }
                                            disabled={savingDecision}
                                        >
                                            {allActionsSelected
                                                ? "Clear all"
                                                : "Select all"}
                                        </button>

                                        <button
                                            type="button"
                                            onClick={
                                                clearActionSelection
                                            }
                                            disabled={
                                                savingDecision ||
                                                selectedActionIds.size ===
                                                0
                                            }
                                        >
                                            Clear selection
                                        </button>
                                    </div>
                                )}

                                <div className="recovery-action-list">
                                    {details.recommendation_actions.map(
                                        (action) => {
                                            const decisionStatus =
                                                action.decision_status ??
                                                "Pending";

                                            return (
                                                <article
                                                    key={
                                                        action
                                                            .recommendation_action_id
                                                    }
                                                    className={`recovery-action-card decision-${decisionStatus.toLowerCase()}`}
                                                >
                                                    <label className="action-selection">
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedActionIds.has(
                                                                action
                                                                    .recommendation_action_id,
                                                            )}
                                                            disabled={
                                                                savingDecision
                                                            }
                                                            onChange={() =>
                                                                toggleActionSelection(
                                                                    action
                                                                        .recommendation_action_id,
                                                                )
                                                            }
                                                            aria-label={`Select ${action.action_title}`}
                                                        />
                                                    </label>

                                                    <div className="action-sequence">
                                                        {
                                                            action.sequence_number
                                                        }
                                                    </div>

                                                    <div className="action-content">
                                                        <div className="action-title-row">
                                                            <h4>
                                                                {
                                                                    action.action_title
                                                                }
                                                            </h4>

                                                            <div className="action-title-actions">
                                                                <span
                                                                    className={`decision-badge ${decisionStatus.toLowerCase()}`}
                                                                >
                                                                    {decisionStatus}
                                                                </span>

                                                                <span className="action-minutes">
                                                                    +
                                                                    {
                                                                        action
                                                                            .estimated_minutes_saved
                                                                    }{" "}
                                                                    min
                                                                </span>
                                                            </div>
                                                        </div>

                                                        <p>
                                                            {
                                                                action
                                                                    .action_description
                                                            }
                                                        </p>

                                                        <div className="action-meta">
                                                            <span>
                                                                Owner:{" "}
                                                                {action.owner_role ??
                                                                    "Warehouse team"}
                                                            </span>

                                                            <span>
                                                                {actionResourceSummary(
                                                                    action,
                                                                )}
                                                            </span>

                                                            {action.start_by && (
                                                                <span>
                                                                    Start by:{" "}
                                                                    {formatDate(
                                                                        action.start_by,
                                                                    )}
                                                                </span>
                                                            )}

                                                            {action.decision_by && (
                                                                <span>
                                                                    Decision by:{" "}
                                                                    {
                                                                        action
                                                                            .decision_by
                                                                    }
                                                                </span>
                                                            )}

                                                            {action.decision_at && (
                                                                <span>
                                                                    Decision at:{" "}
                                                                    {formatDate(
                                                                        action
                                                                            .decision_at,
                                                                    )}
                                                                </span>
                                                            )}
                                                        </div>

                                                        {action.decision_notes && (
                                                            <p className="decision-notes">
                                                                {
                                                                    action
                                                                        .decision_notes
                                                                }
                                                            </p>
                                                        )}
                                                    </div>
                                                </article>
                                            );
                                        },
                                    )}

                                    {actionCount === 0 && (
                                        <p>
                                            No structured recovery
                                            actions have been generated.
                                        </p>
                                    )}
                                </div>
                            </section>

                            <section className="drawer-section impact-panel">
                                <div className="drawer-section-heading">
                                    <div>
                                        <span className="drawer-section-label">
                                            Live What-If simulation
                                        </span>

                                        <h3>
                                            Impact of selected actions
                                        </h3>
                                    </div>

                                    {whatIfSimulation && (
                                        <span
                                            className={`impact-status ${whatIfSimulation.scenario
                                                .sla_recovered
                                                ? "recovered"
                                                : "at-risk"
                                                }`}
                                        >
                                            {whatIfSimulation.scenario
                                                .sla_recovered
                                                ? "SLA recovered"
                                                : "SLA at risk"}
                                        </span>
                                    )}
                                </div>

                                <div className="what-if-controls">
                                    <label className="what-if-number-control">
                                        <span>Extra loaders</span>

                                        <div>
                                            <button
                                                type="button"
                                                disabled={extraLoaders <= 0}
                                                onClick={() =>
                                                    setExtraLoaders(
                                                        (current) =>
                                                            Math.max(
                                                                0,
                                                                current - 1,
                                                            ),
                                                    )
                                                }
                                                aria-label="Remove one extra loader"
                                            >
                                                −
                                            </button>

                                            <strong>
                                                {extraLoaders}
                                            </strong>

                                            <button
                                                type="button"
                                                disabled={extraLoaders >= 5}
                                                onClick={() =>
                                                    setExtraLoaders(
                                                        (current) =>
                                                            Math.min(
                                                                5,
                                                                current + 1,
                                                            ),
                                                    )
                                                }
                                                aria-label="Add one extra loader"
                                            >
                                                +
                                            </button>
                                        </div>
                                    </label>

                                    <label className="what-if-number-control">
                                        <span>Extra forklifts</span>

                                        <div>
                                            <button
                                                type="button"
                                                disabled={extraForklifts <= 0}
                                                onClick={() =>
                                                    setExtraForklifts(
                                                        (current) =>
                                                            Math.max(
                                                                0,
                                                                current - 1,
                                                            ),
                                                    )
                                                }
                                                aria-label="Remove one extra forklift"
                                            >
                                                −
                                            </button>

                                            <strong>
                                                {extraForklifts}
                                            </strong>

                                            <button
                                                type="button"
                                                disabled={extraForklifts >= 5}
                                                onClick={() =>
                                                    setExtraForklifts(
                                                        (current) =>
                                                            Math.min(
                                                                5,
                                                                current + 1,
                                                            ),
                                                    )
                                                }
                                                aria-label="Add one extra forklift"
                                            >
                                                +
                                            </button>
                                        </div>
                                    </label>

                                    <label className="what-if-toggle-control">
                                        <input
                                            type="checkbox"
                                            checked={preStageProducts}
                                            onChange={(event) =>
                                                setPreStageProducts(
                                                    event.target.checked,
                                                )
                                            }
                                        />

                                        <span>
                                            Pre-stage products
                                        </span>
                                    </label>
                                </div>

                                {whatIfLoading && (
                                    <div className="simulation-overlay">
                                        <div className="simulation-spinner" />

                                        <strong>
                                            Running AI optimization
                                        </strong>

                                        <span>
                                            Evaluating labor, equipment,
                                            recovery actions, and SLA impact...
                                        </span>
                                    </div>
                                )}

                                {whatIfError && (
                                    <div className="table-error">
                                        {whatIfError}
                                    </div>
                                )}

                                {!whatIfLoading &&
                                    !whatIfError &&
                                    whatIfSimulation && (
                                        <>
                                            <div className="ai-value-comparison">
                                                <article className="ai-value-column baseline">
                                                    <span className="ai-value-label">
                                                        Without recovery actions
                                                    </span>

                                                    <div>
                                                        <span>Turn time</span>

                                                        <strong>
                                                            {
                                                                whatIfSimulation.baseline
                                                                    .predicted_turn_time_minutes
                                                            }{" "}
                                                            min
                                                        </strong>
                                                    </div>

                                                    <div>
                                                        <span>Risk score</span>

                                                        <strong>
                                                            {
                                                                whatIfSimulation.baseline
                                                                    .turn_risk_score
                                                            }
                                                            /100
                                                        </strong>
                                                    </div>

                                                    <div>
                                                        <span>Detention exposure</span>

                                                        <strong>
                                                            {formatCurrency(
                                                                whatIfSimulation.baseline
                                                                    .detention_exposure,
                                                            )}
                                                        </strong>
                                                    </div>

                                                    <div>
                                                        <span>SLA result</span>

                                                        <strong className="negative-impact">
                                                            {whatIfSimulation.baseline
                                                                .predicted_turn_time_minutes >
                                                                whatIfSimulation.baseline
                                                                    .sla_minutes
                                                                ? "Miss predicted"
                                                                : "Within SLA"}
                                                        </strong>
                                                    </div>
                                                </article>

                                                <div className="ai-value-divider">
                                                    <span>AI</span>
                                                    <strong>→</strong>
                                                </div>

                                                <article className="ai-value-column optimized">
                                                    <span className="ai-value-label">
                                                        With simulated plan
                                                    </span>

                                                    <div>
                                                        <span>Turn time</span>

                                                        <strong>
                                                            {
                                                                whatIfSimulation.scenario
                                                                    .projected_turn_time_minutes
                                                            }{" "}
                                                            min
                                                        </strong>
                                                    </div>

                                                    <div>
                                                        <span>Risk score</span>

                                                        <strong>
                                                            {
                                                                whatIfSimulation.scenario
                                                                    .projected_risk_score
                                                            }
                                                            /100
                                                        </strong>
                                                    </div>

                                                    <div>
                                                        <span>Detention exposure</span>

                                                        <strong>
                                                            {formatCurrency(
                                                                whatIfSimulation.scenario
                                                                    .projected_detention_exposure,
                                                            )}
                                                        </strong>
                                                    </div>

                                                    <div>
                                                        <span>SLA result</span>

                                                        <strong
                                                            className={
                                                                whatIfSimulation.scenario
                                                                    .sla_recovered
                                                                    ? "positive-impact"
                                                                    : "negative-impact"
                                                            }
                                                        >
                                                            {whatIfSimulation.scenario
                                                                .sla_recovered
                                                                ? "Recovered"
                                                                : "At risk"}
                                                        </strong>
                                                    </div>

                                                    <div className="ai-net-value">
                                                        <span>Net savings</span>

                                                        <strong
                                                            className={
                                                                whatIfSimulation.scenario
                                                                    .net_savings >= 0
                                                                    ? "positive-impact"
                                                                    : "negative-impact"
                                                            }
                                                        >
                                                            {formatCurrency(
                                                                whatIfSimulation.scenario
                                                                    .net_savings,
                                                            )}
                                                        </strong>
                                                    </div>
                                                </article>
                                            </div>
                                            <div className="simulation-insights-grid">
                                                <article className="simulation-insight-card">
                                                    <span className="drawer-section-label">
                                                        Top contributor
                                                    </span>

                                                    {topContributor ? (
                                                        <>
                                                            <strong>
                                                                {topContributor.label}
                                                            </strong>

                                                            <p>
                                                                Estimated contribution of{" "}
                                                                <b>
                                                                    {
                                                                        topContributor
                                                                            .minutesSaved
                                                                    }{" "}
                                                                    minutes
                                                                </b>{" "}
                                                                to the simulated recovery.
                                                            </p>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <strong>
                                                                No recovery action selected
                                                            </strong>

                                                            <p>
                                                                Select an AI action or adjust
                                                                warehouse resources.
                                                            </p>
                                                        </>
                                                    )}
                                                </article>

                                                <article className="simulation-insight-card">
                                                    <span className="drawer-section-label">
                                                        Simulation confidence
                                                    </span>

                                                    <strong>
                                                        {simulationConfidence ?? "—"}%
                                                    </strong>

                                                    <p>{confidenceLabel}</p>

                                                    <div className="confidence-track">
                                                        <div
                                                            className="confidence-fill"
                                                            style={{
                                                                width: `${simulationConfidence ?? 0
                                                                    }%`,
                                                            }}
                                                        />
                                                    </div>
                                                </article>
                                            </div>
                                            <div className="impact-comparison">
                                                <div className="impact-column">
                                                    <span>
                                                        Baseline prediction
                                                    </span>

                                                    <strong>
                                                        {
                                                            whatIfSimulation
                                                                .baseline
                                                                .predicted_turn_time_minutes
                                                        }
                                                        <small> min</small>
                                                    </strong>

                                                    <p>
                                                        Risk score{" "}
                                                        {
                                                            whatIfSimulation
                                                                .baseline
                                                                .turn_risk_score
                                                        }
                                                        /100
                                                    </p>
                                                </div>

                                                <div className="impact-arrow">
                                                    →
                                                </div>

                                                <div className="impact-column preview">
                                                    <span>
                                                        Simulated outcome
                                                    </span>

                                                    <strong>
                                                        {
                                                            whatIfSimulation
                                                                .scenario
                                                                .projected_turn_time_minutes
                                                        }
                                                        <small> min</small>
                                                    </strong>

                                                    <p>
                                                        {whatIfSimulation
                                                            .scenario
                                                            .sla_recovered
                                                            ? `${Math.max(
                                                                0,
                                                                whatIfSimulation
                                                                    .baseline
                                                                    .sla_minutes -
                                                                whatIfSimulation
                                                                    .scenario
                                                                    .projected_turn_time_minutes,
                                                            )} minutes within SLA`
                                                            : `${Math.max(
                                                                0,
                                                                whatIfSimulation
                                                                    .scenario
                                                                    .projected_turn_time_minutes -
                                                                whatIfSimulation
                                                                    .baseline
                                                                    .sla_minutes,
                                                            )} minutes above SLA`}
                                                    </p>
                                                </div>
                                            </div>

                                            <div className="impact-metrics-grid">
                                                <div>
                                                    <span>
                                                        Selected AI actions
                                                    </span>

                                                    <strong>
                                                        {
                                                            whatIfSimulation
                                                                .selected_action_ids
                                                                .length
                                                        }
                                                    </strong>
                                                </div>

                                                <div>
                                                    <span>
                                                        Total minutes saved
                                                    </span>

                                                    <strong>
                                                        {
                                                            whatIfSimulation
                                                                .scenario
                                                                .minutes_saved
                                                        }{" "}
                                                        min
                                                    </strong>
                                                </div>

                                                <div>
                                                    <span>
                                                        Projected risk score
                                                    </span>

                                                    <strong>
                                                        {
                                                            whatIfSimulation
                                                                .scenario
                                                                .projected_risk_score
                                                        }
                                                        /100
                                                    </strong>
                                                </div>

                                                <div>
                                                    <span>
                                                        Recovery probability
                                                    </span>

                                                    <strong>
                                                        {formatPercent(
                                                            whatIfSimulation
                                                                .scenario
                                                                .projected_recovery_probability,
                                                        )}
                                                    </strong>
                                                </div>

                                                <div>
                                                    <span>
                                                        Action cost
                                                    </span>

                                                    <strong>
                                                        {formatCurrency(
                                                            whatIfSimulation
                                                                .scenario
                                                                .action_cost,
                                                        )}
                                                    </strong>
                                                </div>

                                                <div>
                                                    <span>
                                                        Gross savings
                                                    </span>

                                                    <strong>
                                                        {formatCurrency(
                                                            whatIfSimulation
                                                                .scenario
                                                                .gross_savings,
                                                        )}
                                                    </strong>
                                                </div>

                                                <div>
                                                    <span>
                                                        Projected detention
                                                    </span>

                                                    <strong>
                                                        {formatCurrency(
                                                            whatIfSimulation
                                                                .scenario
                                                                .projected_detention_exposure,
                                                        )}
                                                    </strong>
                                                </div>

                                                <div>
                                                    <span>
                                                        Net savings
                                                    </span>

                                                    <strong
                                                        className={
                                                            whatIfSimulation
                                                                .scenario
                                                                .net_savings >= 0
                                                                ? "positive-impact"
                                                                : "negative-impact"
                                                        }
                                                    >
                                                        {formatCurrency(
                                                            whatIfSimulation
                                                                .scenario
                                                                .net_savings,
                                                        )}
                                                    </strong>
                                                </div>
                                            </div>

                                            <div className="sla-progress">
                                                <div className="sla-progress-heading">
                                                    <span>
                                                        Projected SLA usage
                                                    </span>

                                                    <strong>
                                                        {Math.round(
                                                            (
                                                                whatIfSimulation
                                                                    .scenario
                                                                    .projected_turn_time_minutes /
                                                                whatIfSimulation
                                                                    .baseline
                                                                    .sla_minutes
                                                            ) * 100,
                                                        )}
                                                        %
                                                    </strong>
                                                </div>

                                                <div className="sla-progress-track">
                                                    <div
                                                        className={`sla-progress-fill ${whatIfSimulation
                                                            .scenario
                                                            .sla_recovered
                                                            ? "recovered"
                                                            : "at-risk"
                                                            }`}
                                                        style={{
                                                            width: `${Math.min(
                                                                100,
                                                                Math.round(
                                                                    (
                                                                        whatIfSimulation
                                                                            .scenario
                                                                            .projected_turn_time_minutes /
                                                                        whatIfSimulation
                                                                            .baseline
                                                                            .sla_minutes
                                                                    ) * 100,
                                                                ),
                                                            )}%`,
                                                        }}
                                                    />
                                                </div>

                                                <div className="sla-progress-labels">
                                                    <span>0 min</span>

                                                    <span>
                                                        SLA target:{" "}
                                                        {
                                                            whatIfSimulation
                                                                .baseline
                                                                .sla_minutes
                                                        }{" "}
                                                        min
                                                    </span>
                                                </div>
                                            </div>
                                        </>
                                    )}

                                {!whatIfLoading &&
                                    !whatIfError &&
                                    !whatIfSimulation && (
                                        <div className="simulation-state">
                                            Select recovery actions or adjust
                                            warehouse resources to run a
                                            simulation.
                                        </div>
                                    )}
                            </section>

                            <AppointmentCopilot
                                appointmentId={
                                    selectedAppointment.appt_id
                                }
                                recommendationId={
                                    details.recommendation
                                        ?.recommendation_id ?? null
                                }
                                recommendationActions={
                                    details.recommendation_actions
                                }
                                selectedActionIds={
                                    Array.from(selectedActionIds)
                                }
                                extraLoaders={extraLoaders}
                                extraForklifts={extraForklifts}
                                preStageProducts={
                                    preStageProducts
                                }
                                onRefresh={onRefresh}
                            />

                            <section className="drawer-section recovery-value-section">
                                <span className="drawer-section-label">
                                    Financial impact
                                </span>

                                <div className="details-grid">
                                    <div>
                                        <span>
                                            Loss without action
                                        </span>

                                        <strong>
                                            {formatCurrency(
                                                recommendation
                                                    ?.estimated_loss_without_action,
                                            )}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>
                                            Accepted action cost
                                        </span>

                                        <strong>
                                            {formatCurrency(
                                                recovery
                                                    ?.accepted_action_cost ??
                                                recommendation
                                                    ?.estimated_cost_of_action,
                                            )}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>
                                            Estimated savings
                                        </span>

                                        <strong>
                                            {formatCurrency(
                                                recommendation
                                                    ?.estimated_savings,
                                            )}
                                        </strong>
                                    </div>

                                    <div>
                                        <span>
                                            Recovery probability
                                        </span>

                                        <strong>
                                            {formatPercent(
                                                prediction
                                                    ?.sla_recovery_probability,
                                            )}
                                        </strong>
                                    </div>
                                </div>
                            </section>


                            <section className="drawer-section">
                                <div className="drawer-section-heading">
                                    <div>
                                        <span className="drawer-section-label">
                                            Products
                                        </span>

                                        <h3>
                                            Appointment load
                                        </h3>
                                    </div>

                                    <span className="appointment-total">
                                        {details.products.length}{" "}
                                        lines
                                    </span>
                                </div>

                                <div className="product-list">
                                    {details.products.map(
                                        (product) => (
                                            <article
                                                key={product.product_id}
                                                className="product-card"
                                            >
                                                <div>
                                                    <strong>
                                                        {
                                                            product.product_name
                                                        }
                                                    </strong>

                                                    <span>
                                                        {product.sku} ·{" "}
                                                        {product.category}
                                                    </span>
                                                </div>

                                                <div className="product-quantity">
                                                    <strong>
                                                        {
                                                            product
                                                                .pallet_count
                                                        }
                                                    </strong>

                                                    <span>pallets</span>
                                                </div>

                                                <div className="product-meta">
                                                    <span>
                                                        {
                                                            product
                                                                .temperature_zone
                                                        }
                                                    </span>

                                                    <span>
                                                        {
                                                            product
                                                                .handling_type
                                                        }
                                                    </span>

                                                    <span>
                                                        {product.quantity}{" "}
                                                        units
                                                    </span>
                                                </div>
                                            </article>
                                        ),
                                    )}
                                </div>
                            </section>


                            <section className="drawer-section">
                                <span className="drawer-section-label">
                                    Operational timeline
                                </span>

                                <h3>
                                    Appointment events
                                </h3>

                                <div className="timeline">
                                    {details.events.map((event) => {
                                        const eventClass = event.event_type
                                            .toLowerCase()
                                            .replaceAll("_", "-");

                                        return (
                                            <div
                                                key={`${event.event_type}-${event.event_id}`}
                                                className={`timeline-item timeline-${eventClass}`}
                                            >
                                                <div className="timeline-marker" />

                                                <div>
                                                    <strong>
                                                        {formatEventType(
                                                            event.event_type,
                                                        )}
                                                    </strong>

                                                    <span>
                                                        {formatDate(
                                                            event.event_time,
                                                        )}
                                                    </span>

                                                    {event.notes && (
                                                        <p>{event.notes}</p>
                                                    )}

                                                    {event.performed_by && (
                                                        <span className="timeline-actor">
                                                            By {event.performed_by}
                                                        </span>
                                                    )}

                                                    {(event.old_value !== null ||
                                                        event.new_value !== null) && (
                                                        <div className="timeline-change">
                                                            {event.field_name && (
                                                                <span className="timeline-field">
                                                                    {event.field_name.replaceAll("_", " ")}
                                                                </span>
                                                            )}
                                                            <div>
                                                                <span className="timeline-old-value">
                                                                    {event.old_value ?? "Not set"}
                                                                </span>
                                                                <span aria-hidden="true">→</span>
                                                                <strong>
                                                                    {event.new_value ?? "Removed"}
                                                                </strong>
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}

                                    {details.events.length === 0 && (
                                        <p className="timeline-empty">
                                            No operational events are available.
                                        </p>
                                    )}
                                </div>
                            </section>


                            {decisionError && (
                                <div className="table-error">
                                    {decisionError}
                                </div>
                            )}

                            <div className="drawer-action-bar">
                                <button
                                    type="button"
                                    className="primary-button"
                                    disabled={
                                        savingDecision ||
                                        selectedActionIds.size === 0
                                    }
                                    onClick={() =>
                                        void applyDecision(
                                            "Accepted",
                                        )
                                    }
                                >
                                    {savingDecision
                                        ? "Saving..."
                                        : "Accept selected"}
                                </button>

                                <button
                                    type="button"
                                    className="secondary-button"
                                    disabled={
                                        savingDecision ||
                                        selectedActionIds.size === 0
                                    }
                                    onClick={() =>
                                        void applyDecision(
                                            "Rejected",
                                        )
                                    }
                                >
                                    Reject selected
                                </button>

                                <button
                                    type="button"
                                    className="secondary-button"
                                    disabled={
                                        savingDecision ||
                                        selectedActionIds.size === 0
                                    }
                                    onClick={() =>
                                        void applyDecision(
                                            "Pending",
                                        )
                                    }
                                >
                                    Reset to pending
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </aside>
            {editOpen && details && (
                <EditAppointmentDrawer
                    open={editOpen}
                    details={details}
                    onClose={() => setEditOpen(false)}
                    onUpdated={onRefresh}
                />
            )}
        </>
    );
}