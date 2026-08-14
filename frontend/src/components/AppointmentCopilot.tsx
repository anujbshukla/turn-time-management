import {
    useEffect,
    useRef,
    useState,
} from "react";

import type {
    FormEvent,
} from "react";

import type {
    AppointmentCopilotResponse,
    CopilotActionIntent,
    CopilotConversationMessage,
} from "../types/copilot";

import {
    askAppointmentCopilot,
} from "../services/copilot";

import {
    updateRecommendationDecisions,
} from "../services/recommendations";

import type {
    RecommendationAction,
} from "../types/appointmentDetails";


type AppointmentCopilotProps = {
    appointmentId: string;

    recommendationId: number | null;

    recommendationActions: RecommendationAction[];

    selectedActionIds: number[];

    extraLoaders: number;

    extraForklifts: number;

    preStageProducts: boolean;

    onRefresh: () => void | Promise<void>;
};


type DisplayMessage = {
    id: string;

    role: "user" | "assistant";

    content: string;

    facts?: AppointmentCopilotResponse["facts"];

    actionIntent?: CopilotActionIntent | null;
};


export function AppointmentCopilot({
    appointmentId,
    recommendationId,
    recommendationActions,
    selectedActionIds,
    extraLoaders,
    extraForklifts,
    preStageProducts,
    onRefresh,
}: AppointmentCopilotProps) {
    const [question, setQuestion] =
        useState("");

    const [
        executingActionId,
        setExecutingActionId,
    ] = useState<string | null>(null);

    const [
        actionExecutionError,
        setActionExecutionError,
    ] = useState<string | null>(null);

    const [messages, setMessages] =
        useState<DisplayMessage[]>([]);

    const conversationRef =
        useRef<HTMLDivElement | null>(null);

    const [loading, setLoading] =
        useState(false);

    const [error, setError] =
        useState<string | null>(null);


    useEffect(() => {
        setQuestion("");
        setMessages([]);
        setError(null);
        setActionExecutionError(null);
        setExecutingActionId(null);
    }, [appointmentId]);


    useEffect(() => {
        if (
            messages.length === 0 &&
            !loading
        ) {
            return;
        }

        const frameId =
            window.requestAnimationFrame(() => {
                const conversation =
                    conversationRef.current;

                if (!conversation) {
                    return;
                }

                conversation.scrollTo({
                    top:
                        conversation.scrollHeight,

                    behavior: "smooth",
                });
            });

        return () => {
            window.cancelAnimationFrame(
                frameId,
            );
        };
    }, [messages, loading]);


    async function submitQuestion(
        requestedQuestion?: string,
    ) {
        const finalQuestion =
            requestedQuestion?.trim() ??
            question.trim();

        if (
            !finalQuestion ||
            loading ||
            executingActionId !== null
        ) {
            return;
        }

        const userMessage:
            DisplayMessage = {
            id: crypto.randomUUID(),

            role: "user",

            content: finalQuestion,
        };

        const conversationHistory:
            CopilotConversationMessage[] =
            messages.map((message) => ({
                role: message.role,

                content: message.content,
            }));

        setMessages((current) => [
            ...current,
            userMessage,
        ]);

        setQuestion("");
        setLoading(true);
        setError(null);
        setActionExecutionError(null);

        try {
            const result =
                await askAppointmentCopilot(
                    appointmentId,
                    {
                        question:
                            finalQuestion,

                        what_if: {
                            selected_action_ids:
                                selectedActionIds,

                            extra_loaders:
                                extraLoaders,

                            extra_forklifts:
                                extraForklifts,

                            pre_stage_products:
                                preStageProducts,
                        },

                        conversation_history:
                            conversationHistory,
                    },
                );

            const assistantMessage:
                DisplayMessage = {
                id: crypto.randomUUID(),

                role: "assistant",

                content: result.answer,

                facts: result.facts,

                actionIntent:
                    result.action_intent,
            };

            setMessages((current) => [
                ...current,
                assistantMessage,
            ]);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "Unable to ask Copilot.",
            );
        } finally {
            setLoading(false);
        }
    }


    function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();

        void submitQuestion();
    }


    function getActionsForIntent(
        intent: CopilotActionIntent,
    ): RecommendationAction[] {
        const actionIdSet = new Set(
            intent.action_ids,
        );

        return recommendationActions.filter(
            (action) =>
                actionIdSet.has(
                    action
                        .recommendation_action_id,
                ),
        );
    }


    async function confirmCopilotAction(
        messageId: string,
        intent: CopilotActionIntent,
    ) {
        if (
            recommendationId == null ||
            intent.action_ids.length === 0
        ) {
            setActionExecutionError(
                "The proposed action cannot be executed because the recommendation or recovery actions are unavailable.",
            );

            return;
        }

        const decisionStatus:
            | "Accepted"
            | "Rejected"
            | null =
            intent.action ===
                "accept_actions"
                ? "Accepted"
                : intent.action ===
                    "reject_actions"
                    ? "Rejected"
                    : null;

        if (decisionStatus === null) {
            setActionExecutionError(
                "This Copilot action is not currently supported by the confirmation card.",
            );

            return;
        }

        const validActionIds = new Set(
            recommendationActions.map(
                (action) =>
                    action
                        .recommendation_action_id,
            ),
        );

        const executableActionIds =
            intent.action_ids.filter(
                (actionId) =>
                    validActionIds.has(
                        actionId,
                    ),
            );

        if (
            executableActionIds.length === 0
        ) {
            setActionExecutionError(
                "None of the proposed action IDs belong to the current recovery plan.",
            );

            return;
        }

        if (
            executableActionIds.length !==
            intent.action_ids.length
        ) {
            setActionExecutionError(
                "One or more proposed actions do not belong to the current recovery plan.",
            );

            return;
        }

        setExecutingActionId(messageId);
        setActionExecutionError(null);

        try {
            await updateRecommendationDecisions(
                recommendationId,
                {
                    decided_by:
                        "Warehouse Supervisor via Copilot",

                    actions:
                        executableActionIds.map(
                            (actionId) => ({
                                recommendation_action_id:
                                    actionId,

                                decision_status:
                                    decisionStatus,
                            }),
                        ),
                },
            );

            const confirmationText =
                decisionStatus ===
                    "Accepted"
                    ? "Confirmed. The selected recovery actions were accepted."
                    : "Confirmed. The selected recovery actions were rejected.";

            setMessages((current) =>
                current.map((message) =>
                    message.id ===
                        messageId
                        ? {
                            ...message,

                            content:
                                `${message.content}\n\n${confirmationText}`,

                            actionIntent:
                                null,
                        }
                        : message,
                ),
            );

            await onRefresh();
        } catch (executionError) {
            setActionExecutionError(
                executionError instanceof Error
                    ? executionError.message
                    : "Unable to execute the Copilot action.",
            );
        } finally {
            setExecutingActionId(null);
        }
    }


    function cancelCopilotAction(
        messageId: string,
    ) {
        setMessages((current) =>
            current.map((message) =>
                message.id === messageId
                    ? {
                        ...message,

                        content:
                            `${message.content}\n\nAction cancelled. No changes were made.`,

                        actionIntent:
                            null,
                    }
                    : message,
            ),
        );

        setActionExecutionError(null);
    }


    return (
        <section className="drawer-section copilot-panel">
            <div className="drawer-section-heading">
                <div>
                    <span className="drawer-section-label">
                        AI Warehouse Copilot
                    </span>

                    <h3>
                        Ask about this appointment
                    </h3>
                </div>

                <div className="copilot-heading-actions">
                    <span className="copilot-grounded-badge">
                        Grounded
                    </span>

                    {messages.length > 0 && (
                        <button
                            type="button"
                            className="copilot-clear-button"
                            disabled={
                                loading ||
                                executingActionId !==
                                null
                            }
                            onClick={() => {
                                setMessages([]);
                                setQuestion("");
                                setError(null);
                                setActionExecutionError(
                                    null,
                                );
                            }}
                        >
                            Clear
                        </button>
                    )}
                </div>
            </div>

            <div className="copilot-suggestions">
                {[
                    "Why is this appointment at risk?",
                    "Which recovery action has the highest impact?",
                    "Can we meet SLA without extra labor?",
                    "What is the projected detention savings?",
                    "Accept the highest-impact action.",
                ].map((suggestion) => (
                    <button
                        key={suggestion}
                        type="button"
                        disabled={
                            loading ||
                            executingActionId !==
                            null
                        }
                        onClick={() =>
                            void submitQuestion(
                                suggestion,
                            )
                        }
                    >
                        {suggestion}
                    </button>
                ))}
            </div>

            <div
                ref={conversationRef}
                className="copilot-conversation"
            >
                {messages.length === 0 &&
                    !loading && (
                        <div className="copilot-empty-state">
                            <strong>
                                Ask about risk,
                                recovery actions,
                                products, SLA, or
                                financial impact.
                            </strong>

                            <span>
                                Copilot answers using
                                this appointment’s live
                                operational data.
                            </span>
                        </div>
                    )}

                {messages.map((message) => {
                    const actionIntent =
                        message.actionIntent;

                    const confirmationIntent =
                        message.role ===
                            "assistant" &&
                            actionIntent
                                ?.confirmation_required &&
                            (
                                actionIntent.action ===
                                "accept_actions" ||
                                actionIntent.action ===
                                "reject_actions"
                            )
                            ? actionIntent
                            : null;

                    const actionsForIntent =
                        confirmationIntent
                            ? getActionsForIntent(
                                confirmationIntent,
                            )
                            : [];

                    const totalMinutesSaved =
                        actionsForIntent.reduce(
                            (
                                total,
                                action,
                            ) =>
                                total +
                                (
                                    action
                                        .estimated_minutes_saved ??
                                    0
                                ),
                            0,
                        );

                    const totalActionCost =
                        actionsForIntent.reduce(
                            (
                                total,
                                action,
                            ) =>
                                total +
                                (
                                    action
                                        .estimated_action_cost ??
                                    0
                                ),
                            0,
                        );

                    const isAcceptAction =
                        confirmationIntent
                            ?.action ===
                        "accept_actions";

                    const allActionIdsResolved =
                        confirmationIntent !=
                        null &&
                        confirmationIntent
                            .action_ids
                            .length > 0 &&
                        actionsForIntent.length ===
                        confirmationIntent
                            .action_ids
                            .length;

                    return (
                        <article
                            key={message.id}
                            className={`copilot-message ${message.role}`}
                        >
                            <span className="copilot-message-role">
                                {message.role ===
                                    "assistant"
                                    ? "Copilot"
                                    : "You"}
                            </span>

                            <p>
                                {message.content}
                            </p>

                            {message.facts &&
                                message.facts
                                    .length >
                                0 && (
                                    <div className="copilot-facts">
                                        {message.facts.map(
                                            (
                                                fact,
                                            ) => (
                                                <div
                                                    key={`${message.id}-${fact.label}`}
                                                >
                                                    <span>
                                                        {
                                                            fact.label
                                                        }
                                                    </span>

                                                    <strong>
                                                        {
                                                            fact.value
                                                        }
                                                    </strong>
                                                </div>
                                            ),
                                        )}
                                    </div>
                                )}

                            {confirmationIntent && (
                                <div className="copilot-action-card">
                                    <div className="copilot-action-card-header">
                                        <div>
                                            <span className="copilot-action-label">
                                                Pending AI
                                                action
                                            </span>

                                            <strong>
                                                {isAcceptAction
                                                    ? "Accept recovery actions"
                                                    : "Reject recovery actions"}
                                            </strong>
                                        </div>

                                        <span className="copilot-confirmation-badge">
                                            Confirmation
                                            required
                                        </span>
                                    </div>

                                    <div className="copilot-action-list">
                                        {actionsForIntent.map(
                                            (
                                                action,
                                            ) => (
                                                <div
                                                    key={
                                                        action
                                                            .recommendation_action_id
                                                    }
                                                    className="copilot-action-list-item"
                                                >
                                                    <div>
                                                        <strong>
                                                            {
                                                                action
                                                                    .action_title
                                                            }
                                                        </strong>

                                                        <span>
                                                            {
                                                                action
                                                                    .action_description
                                                            }
                                                        </span>
                                                    </div>

                                                    <div className="copilot-action-impact">
                                                        <strong>
                                                            +
                                                            {
                                                                action
                                                                    .estimated_minutes_saved
                                                            }{" "}
                                                            min
                                                        </strong>

                                                        <span>
                                                            {(
                                                                action
                                                                    .estimated_action_cost ??
                                                                0
                                                            ).toLocaleString(
                                                                "en-US",
                                                                {
                                                                    style:
                                                                        "currency",

                                                                    currency:
                                                                        "USD",
                                                                },
                                                            )}
                                                        </span>
                                                    </div>
                                                </div>
                                            ),
                                        )}

                                        {confirmationIntent
                                            .action_ids
                                            .length ===
                                            0 && (
                                                <div className="simulation-state">
                                                    Copilot
                                                    recognized
                                                    the command,
                                                    but could not
                                                    determine
                                                    which
                                                    recovery
                                                    actions you
                                                    meant.
                                                </div>
                                            )}

                                        {confirmationIntent
                                            .action_ids
                                            .length >
                                            0 &&
                                            actionsForIntent
                                                .length ===
                                            0 && (
                                                <div className="simulation-state">
                                                    The
                                                    proposed
                                                    action IDs
                                                    were not
                                                    found in
                                                    the current
                                                    recovery
                                                    plan.
                                                </div>
                                            )}

                                        {confirmationIntent
                                            .action_ids
                                            .length >
                                            0 &&
                                            actionsForIntent
                                                .length >
                                            0 &&
                                            !allActionIdsResolved && (
                                                <div className="table-error">
                                                    One or
                                                    more
                                                    proposed
                                                    actions do
                                                    not belong
                                                    to the
                                                    current
                                                    recovery
                                                    plan.
                                                    Confirmation
                                                    has been
                                                    disabled.
                                                </div>
                                            )}
                                    </div>

                                    <div className="copilot-action-summary">
                                        <div>
                                            <span>
                                                Selected
                                                actions
                                            </span>

                                            <strong>
                                                {
                                                    actionsForIntent
                                                        .length
                                                }
                                            </strong>
                                        </div>

                                        <div>
                                            <span>
                                                Estimated
                                                recovery
                                            </span>

                                            <strong>
                                                {
                                                    totalMinutesSaved
                                                }{" "}
                                                min
                                            </strong>
                                        </div>

                                        <div>
                                            <span>
                                                Estimated cost
                                            </span>

                                            <strong>
                                                {totalActionCost.toLocaleString(
                                                    "en-US",
                                                    {
                                                        style:
                                                            "currency",

                                                        currency:
                                                            "USD",
                                                    },
                                                )}
                                            </strong>
                                        </div>
                                    </div>

                                    <div className="copilot-action-buttons">
                                        <button
                                            type="button"
                                            className="primary-button"
                                            disabled={
                                                executingActionId !==
                                                null ||
                                                !allActionIdsResolved
                                            }
                                            onClick={() =>
                                                void confirmCopilotAction(
                                                    message.id,
                                                    confirmationIntent,
                                                )
                                            }
                                        >
                                            {executingActionId ===
                                                message.id
                                                ? "Applying..."
                                                : "Confirm"}
                                        </button>

                                        <button
                                            type="button"
                                            className="secondary-button"
                                            disabled={
                                                executingActionId !==
                                                null
                                            }
                                            onClick={() =>
                                                cancelCopilotAction(
                                                    message.id,
                                                )
                                            }
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                            )}
                        </article>
                    );
                })}

                {loading && (
                    <article className="copilot-message assistant">
                        <span className="copilot-message-role">
                            Copilot
                        </span>

                        <div className="copilot-typing">
                            <span />
                            <span />
                            <span />
                        </div>
                    </article>
                )}
            </div>

            {error && (
                <div
                    className="table-error"
                    role="alert"
                    aria-live="polite"
                >
                    <strong>Copilot request failed</strong>

                    <span>{error}</span>
                </div>
            )}

            {actionExecutionError && (
                <div
                    className="table-error"
                    role="alert"
                    aria-live="assertive"
                >
                    <strong>
                        Action could not be completed
                    </strong>

                    <span>
                        {actionExecutionError}
                    </span>

                    <button
                        type="button"
                        className="copilot-error-dismiss"
                        onClick={() =>
                            setActionExecutionError(null)
                        }
                    >
                        Dismiss
                    </button>
                </div>
            )}

            <form
                className="copilot-input-row"
                onSubmit={handleSubmit}
            >
                <input
                    type="text"
                    value={question}
                    disabled={
                        loading ||
                        executingActionId !== null
                    }
                    placeholder="Ask why, compare actions, or request an operational action..."
                    onChange={(event) =>
                        setQuestion(
                            event.target.value,
                        )
                    }
                />

                <button
                    type="submit"
                    className="primary-button"
                    disabled={
                        loading ||
                        executingActionId !==
                        null ||
                        question.trim()
                            .length === 0
                    }
                >
                    Ask
                </button>
            </form>
        </section>
    );
}