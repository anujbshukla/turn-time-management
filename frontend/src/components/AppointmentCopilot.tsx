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
    CopilotConversationMessage,
} from "../types/copilot";

import {
    askAppointmentCopilot,
} from "../services/copilot";



type AppointmentCopilotProps = {
    appointmentId: string;
    selectedActionIds: number[];
    extraLoaders: number;
    extraForklifts: number;
    preStageProducts: boolean;
};

export function AppointmentCopilot({
    appointmentId,
    selectedActionIds,
    extraLoaders,
    extraForklifts,
    preStageProducts,
}: AppointmentCopilotProps) {
    const [question, setQuestion] =
        useState("");

    type DisplayMessage = {
        id: string;
        role: "user" | "assistant";
        content: string;
        facts?: AppointmentCopilotResponse["facts"];
    };

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
    }, [appointmentId]);

    useEffect(() => {
        if (messages.length === 0 && !loading) {
            return;
        }

        const frameId = window.requestAnimationFrame(
            () => {
                const conversation =
                    conversationRef.current;

                if (!conversation) {
                    return;
                }

                conversation.scrollTo({
                    top: conversation.scrollHeight,
                    behavior: "smooth",
                });
            },
        );

        return () => {
            window.cancelAnimationFrame(frameId);
        };
    }, [messages, loading]);

    async function submitQuestion(
        requestedQuestion?: string,
    ) {
        const finalQuestion =
            requestedQuestion?.trim() ??
            question.trim();

        if (!finalQuestion || loading) {
            return;
        }

        const userMessage: DisplayMessage = {
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

        try {
            const result =
                await askAppointmentCopilot(
                    appointmentId,
                    {
                        question: finalQuestion,

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
            };

            setMessages((current) => [
                ...current,
                assistantMessage,
            ]);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "Unable to ask Copilot",
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
                            disabled={loading}
                            onClick={() => {
                                setMessages([]);
                                setQuestion("");
                                setError(null);
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
                ].map((suggestion) => (
                    <button
                        key={suggestion}
                        type="button"
                        disabled={loading}
                        onClick={() =>
                            void submitQuestion(suggestion)
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
                {messages.length === 0 && !loading && (
                    <div className="copilot-empty-state">
                        <strong>
                            Ask about risk, recovery actions,
                            products, SLA, or financial impact.
                        </strong>

                        <span>
                            Copilot answers using this
                            appointment’s live operational data.
                        </span>
                    </div>
                )}

                {messages.map((message) => (
                    <article
                        key={message.id}
                        className={`copilot-message ${message.role}`}
                    >
                        <span className="copilot-message-role">
                            {message.role === "assistant"
                                ? "Copilot"
                                : "You"}
                        </span>

                        <p>{message.content}</p>

                        {message.facts &&
                            message.facts.length > 0 && (
                                <div className="copilot-facts">
                                    {message.facts.map((fact) => (
                                        <div
                                            key={`${message.id}-${fact.label}`}
                                        >
                                            <span>
                                                {fact.label}
                                            </span>

                                            <strong>
                                                {fact.value}
                                            </strong>
                                        </div>
                                    ))}
                                </div>
                            )}
                    </article>
                ))}

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
                <div className="table-error">
                    {error}
                </div>
            )}

            <form
                className="copilot-input-row"
                onSubmit={handleSubmit}
            >
                <input
                    type="text"
                    value={question}
                    disabled={loading}
                    placeholder="Ask why, compare actions, or request a summary..."
                    onChange={(event) =>
                        setQuestion(event.target.value)
                    }
                />

                <button
                    type="submit"
                    className="primary-button"
                    disabled={
                        loading ||
                        question.trim().length === 0
                    }
                >
                    Ask
                </button>
            </form>
        </section>
    );
}