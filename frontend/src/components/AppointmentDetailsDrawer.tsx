import {
    useEffect,
    useState,
} from "react";

import { useWhatIf } from "../hooks/useWhatIf";

import { AppointmentCopilot } from "./AppointmentCopilot";
import { AppointmentEventHistory } from "./AppointmentEventHistory";
import { AppointmentOperationalIntelligence } from "./AppointmentOperationalIntelligence";
import { AppointmentRecoveryPlan } from "./AppointmentRecoveryPlan";
import { AppointmentRiskAssessment } from "./AppointmentRiskAssessment";
import { AppointmentWhatIfPanel } from "./AppointmentWhatIfPanel";
import { EditAppointmentDialog } from "./EditAppointmentDialog";
import { RescheduleAppointmentDialog } from "./RescheduleAppointmentDialog";
import { ShipmentItemsTable } from "./ShipmentItemsTable";

import {
    updateRecommendationDecisions,
} from "../services/recommendations";

import type {
    ActionDecisionStatus,
} from "../services/recommendations";

import type {
    AppointmentDetailsResponse,
} from "../types/appointmentDetails";

import type {
    AppointmentListItem,
} from "../types/appointments";

type AppointmentDetailsDrawerProps = {
    selectedAppointment:
    AppointmentListItem | null;
    details:
    AppointmentDetailsResponse | null;
    loading: boolean;
    error: string | null;
    onRefresh: () => void;
    onClose: () => void;
};

export function AppointmentDetailsDrawer({
    selectedAppointment,
    details,
    loading,
    error,
    onRefresh,
    onClose,
}: AppointmentDetailsDrawerProps) {
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

    const [
        editAppointmentOpen,
        setEditAppointmentOpen,
    ] = useState(false);

    const [
        rescheduleAppointmentOpen,
        setRescheduleAppointmentOpen,
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
        enabled: Boolean(
            selectedAppointment &&
            details?.prediction,
        ),
    });

    function toggleActionSelection(
        actionId: number,
    ) {
        setSelectedActionIds((current) => {
            const next =
                new Set(current);

            if (next.has(actionId)) {
                next.delete(actionId);
            } else {
                next.add(actionId);
            }

            return next;
        });
    }

    function selectAllActions() {
        if (!details) return;

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
        decisionStatus:
            ActionDecisionStatus,
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
                            action
                                .recommendation_action_id,
                        ),
                    )
                    .map((action) => ({
                        recommendation_action_id:
                            action
                                .recommendation_action_id,
                        decision_status:
                            decisionStatus,
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
        details?.recommendation ?? null;

    const recovery =
        details?.recovery_summary;

    const score =
        prediction?.turn_risk_score ??
        selectedAppointment
            .turn_risk_score ??
        0;

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
                                selectedAppointment
                                    .customer_name ??
                                "Unknown customer"}
                        </p>
                    </div>

                    <div className="appointment-drawer-header-actions">
                        {details && (
                            <>
                                <button
                                    type="button"
                                    className="secondary-button appointment-drawer-action"
                                    disabled={
                                        details.appointment
                                            .status ===
                                        "Completed"
                                    }
                                    onClick={() =>
                                        setEditAppointmentOpen(
                                            true,
                                        )
                                    }
                                >
                                    Edit appointment
                                </button>

                                <button
                                    type="button"
                                    className="secondary-button appointment-drawer-action"
                                    disabled={
                                        details.appointment
                                            .status ===
                                        "Arrived" ||
                                        details.appointment
                                            .status ===
                                        "Waiting" ||
                                        details.appointment
                                            .status ===
                                        "Dock Assigned" ||
                                        details.appointment
                                            .status ===
                                        "In Progress" ||
                                        details.appointment
                                            .status ===
                                        "Completed" ||
                                        Boolean(
                                            details.appointment
                                                .actual_arrival_time,
                                        )
                                    }
                                    onClick={() =>
                                        setRescheduleAppointmentOpen(
                                            true,
                                        )
                                    }
                                >
                                    Reschedule
                                </button>
                            </>
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

                    {!loading &&
                        details &&
                        appointment &&
                        recovery && (
                            <>
                                <section className="drawer-section appointment-operational-intelligence-section">
                                    <AppointmentOperationalIntelligence
                                        appointment={
                                            appointment
                                        }
                                        prediction={
                                            prediction ?? null
                                        }
                                        recovery={recovery}
                                    />
                                </section>

                                <AppointmentRiskAssessment
                                    appointment={
                                        appointment
                                    }
                                    prediction={
                                        prediction ?? null
                                    }
                                    recovery={recovery}
                                    recommendation={
                                        recommendation
                                    }
                                    score={score}
                                />

                                <AppointmentRecoveryPlan
                                    actions={
                                        details
                                            .recommendation_actions
                                    }
                                    recovery={recovery}
                                    selectedActionIds={
                                        selectedActionIds
                                    }
                                    savingDecision={
                                        savingDecision
                                    }
                                    onToggleAction={
                                        toggleActionSelection
                                    }
                                    onSelectAll={
                                        selectAllActions
                                    }
                                    onClearSelection={
                                        clearActionSelection
                                    }
                                />

                                <AppointmentWhatIfPanel
                                    simulation={
                                        whatIfSimulation
                                    }
                                    loading={
                                        whatIfLoading
                                    }
                                    error={whatIfError}
                                    extraLoaders={
                                        extraLoaders
                                    }
                                    setExtraLoaders={
                                        setExtraLoaders
                                    }
                                    extraForklifts={
                                        extraForklifts
                                    }
                                    setExtraForklifts={
                                        setExtraForklifts
                                    }
                                    preStageProducts={
                                        preStageProducts
                                    }
                                    setPreStageProducts={
                                        setPreStageProducts
                                    }
                                />

                                <ShipmentItemsTable
                                    products={
                                        details.products
                                    }
                                />

                                <AppointmentEventHistory
                                    events={details.events}
                                />

                                <AppointmentCopilot
                                    appointmentId={
                                        selectedAppointment.appt_id
                                    }
                                    recommendationId={
                                        recommendation
                                            ?.recommendation_id ??
                                        null
                                    }
                                    recommendationActions={
                                        details
                                            .recommendation_actions
                                    }
                                    selectedActionIds={Array.from(
                                        selectedActionIds,
                                    )}
                                    extraLoaders={
                                        extraLoaders
                                    }
                                    extraForklifts={
                                        extraForklifts
                                    }
                                    preStageProducts={
                                        preStageProducts
                                    }
                                    onRefresh={onRefresh}
                                />

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
                                            selectedActionIds.size ===
                                            0
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
                                            selectedActionIds.size ===
                                            0
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
                                            selectedActionIds.size ===
                                            0
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

            {details && (
                <>
                    <EditAppointmentDialog
                        open={
                            editAppointmentOpen
                        }
                        details={details}
                        onClose={() =>
                            setEditAppointmentOpen(
                                false,
                            )
                        }
                        onSaved={onRefresh}
                    />

                    <RescheduleAppointmentDialog
                        open={
                            rescheduleAppointmentOpen
                        }
                        appointment={
                            details.appointment
                        }
                        onClose={() =>
                            setRescheduleAppointmentOpen(
                                false,
                            )
                        }
                        onSaved={onRefresh}
                    />
                </>
            )}
        </>
    );
}
