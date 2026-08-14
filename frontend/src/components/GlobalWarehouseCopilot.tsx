import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";

import { askGlobalCopilot } from "../services/dashboard";
import {
    createAppointment,
    getAppointmentReferenceData,
} from "../services/appointments";
import type {
    AppointmentFilters,
    AppointmentReferenceData,
    CreateAppointmentResponse,
} from "../types/appointments";
import type {
    DashboardResponse,
    DashboardWhatIfRequest,
    GlobalCopilotActionIntent,
    GlobalCopilotBookingDraft,
    GlobalCopilotConversationMessage,
    GlobalCopilotFact,
    GlobalCopilotQuickAction,
} from "../types/dashboard";

type GlobalWarehouseCopilotProps = {
    dashboard: DashboardResponse | null;
    loading: boolean;
    activeFilters: AppointmentFilters;
    onApplyFilters: (filters: AppointmentFilters) => void;
    onClearFilters: () => void;
    onOpenAppointment: (appointmentId: string) => void;
    onRunWhatIf: (request: DashboardWhatIfRequest) => void;
    onAppointmentCreated: (result: CreateAppointmentResponse) => void | Promise<void>;
};

type DisplayMessage = {
    id: string;
    role: "user" | "assistant";
    content: string;
    facts?: GlobalCopilotFact[];
    quickActions?: GlobalCopilotQuickAction[];
    actionIntent?: GlobalCopilotActionIntent | null;
};

const INITIAL_SUGGESTIONS = [
    "Book a new appointment",
    "Which appointments need attention?",
    "Why are SLAs being missed?",
    "Which recovery plan is most effective?",
    "How much value have recommendations created?",
    "Run a scenario with 1 extra loader and 1 forklift",
];


function isBookingConfirmationPhrase(value: string) {
    const normalized = value
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, "")
        .replace(/\s+/g, " ");

    return new Set([
        "confirm",
        "confirm booking",
        "book it",
        "create it",
        "create appointment",
        "yes confirm",
        "yes book it",
        "proceed",
        "proceed with booking",
    ]).has(normalized);
}

export function GlobalWarehouseCopilot({
    dashboard,
    loading,
    activeFilters,
    onApplyFilters,
    onClearFilters,
    onOpenAppointment,
    onRunWhatIf,
    onAppointmentCreated,
}: GlobalWarehouseCopilotProps) {
    const [expanded, setExpanded] = useState(false);
    const [question, setQuestion] = useState("");
    const [messages, setMessages] = useState<DisplayMessage[]>([]);
    const [suggestions, setSuggestions] = useState(INITIAL_SUGGESTIONS);
    const [requestLoading, setRequestLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [executingMessageId, setExecutingMessageId] = useState<string | null>(null);
    const [bookingDraft, setBookingDraft] = useState<GlobalCopilotBookingDraft | null>(null);
    const [referenceData, setReferenceData] = useState<AppointmentReferenceData | null>(null);
    const conversationRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        let active = true;

        void getAppointmentReferenceData()
            .then((data) => {
                if (active) setReferenceData(data);
            })
            .catch(() => {
                if (active) setReferenceData(null);
            });

        return () => {
            active = false;
        };
    }, []);

    const operationalBrief = useMemo(() => {
        if (loading && !dashboard) return "Preparing the latest operational brief…";
        if (!dashboard) return "Connect the dashboard feed to generate a live operational brief.";

        const critical = dashboard.risk_distribution.find(
            (item) => item.risk_level.toLowerCase() === "critical",
        )?.appointment_count ?? 0;

        return `${dashboard.summary.late_arrivals.toLocaleString()} late arrivals, ${dashboard.summary.sla_misses.toLocaleString()} SLA misses and ${critical.toLocaleString()} Critical-risk appointments are visible in the current operating window.`;
    }, [dashboard, loading]);

    useEffect(() => {
        if (!expanded) return;
        const frame = window.requestAnimationFrame(() => {
            conversationRef.current?.scrollTo({
                top: conversationRef.current.scrollHeight,
                behavior: "smooth",
            });
        });
        return () => window.cancelAnimationFrame(frame);
    }, [messages, requestLoading, expanded]);

    async function confirmBookingDraft(
        draft: GlobalCopilotBookingDraft,
        sourceMessageId?: string,
    ) {
        if (
            !draft.customer_id ||
            !draft.carrier_id ||
            !draft.facility_id ||
            !draft.scheduled_time ||
            !draft.appointment_type ||
            draft.products.length === 0
        ) {
            throw new Error(
                "The booking draft is incomplete. Continue answering Copilot's prompts before confirming.",
            );
        }

        const result = await createAppointment({
            customer_id: draft.customer_id,
            customer_name: draft.customer_label ?? null,
            facility_id: draft.facility_id,
            carrier_id: draft.carrier_id,
            assigned_dock_id: draft.assigned_dock_id ?? null,
            scheduled_time: draft.scheduled_time,
            estimated_arrival_time: null,
            status: "Scheduled",
            appointment_type: draft.appointment_type,
            load_type: draft.load_type || "Palletized",
            trailer_number: null,
            pallet_count: 0,
            sku_count: 0,
            total_weight: null,
            total_cube: null,
            priority: draft.priority || 1,
            sla_minutes: draft.sla_minutes || 120,
            detention_cost_per_hour:
                draft.detention_cost_per_hour ?? 100,
            distance_band: "Regional",
            traffic_severity: 0,
            weather_severity: 0,
            surge_indicator: false,
            products: draft.products.map((product) => ({
                product_id: product.product_id,
                quantity: product.quantity,
            })),
        });

        setBookingDraft(null);
        setMessages((current) => [
            ...current.map((currentMessage) =>
                sourceMessageId &&
                currentMessage.id === sourceMessageId
                    ? {
                        ...currentMessage,
                        actionIntent: null,
                    }
                    : currentMessage,
            ),
            {
                id: crypto.randomUUID(),
                role: "assistant",
                content:
                    `${result.message} Booking confirmed as ${result.appt_id}.`,
            },
        ]);

        await onAppointmentCreated(result);
    }

    async function submitQuestion(requestedQuestion?: string) {
        const finalQuestion = requestedQuestion?.trim() ?? question.trim();
        if (!finalQuestion || requestLoading || executingMessageId) return;

        setExpanded(true);
        setQuestion("");
        setError(null);

        if (
            bookingDraft &&
            isBookingConfirmationPhrase(finalQuestion)
        ) {
            const userMessage: DisplayMessage = {
                id: crypto.randomUUID(),
                role: "user",
                content: finalQuestion,
            };

            setMessages((current) => [
                ...current,
                userMessage,
            ]);
            setExecutingMessageId("typed-confirmation");

            try {
                await confirmBookingDraft(bookingDraft);
            } catch (confirmationError) {
                setError(
                    confirmationError instanceof Error
                        ? confirmationError.message
                        : "Unable to confirm the appointment booking.",
                );
            } finally {
                setExecutingMessageId(null);
            }

            return;
        }

        // Keep the request within the API validation limit during longer
        // booking conversations. The booking draft carries the structured
        // state, so older chat messages are not required for execution.
        const history: GlobalCopilotConversationMessage[] = messages
            .slice(-40)
            .map((message) => ({
                role: message.role,
                content: message.content,
            }));

        const userMessage: DisplayMessage = {
            id: crypto.randomUUID(),
            role: "user",
            content: finalQuestion,
        };
        setMessages((current) => [...current, userMessage]);
        setRequestLoading(true);

        try {
            const result = await askGlobalCopilot({
                question: finalQuestion,
                conversation_history: history,
                facility_id: activeFilters.facilityId,
                booking_draft: bookingDraft,
            });
            if (result.action_intent?.action === "book_appointment") {
                if (result.action_intent.metadata.booking_state === "cancelled") {
                    setBookingDraft(null);
                } else {
                    setBookingDraft(result.action_intent.booking_draft ?? null);
                }
            }

            // Safe navigation actions execute immediately when the user has
            // explicitly asked Copilot to open an appointment. Booking and
            // other data-changing actions continue to use confirmation.
            if (
                result.action_intent?.action === "open_appointment" &&
                !result.action_intent.confirmation_required
            ) {
                const appointmentId = result.action_intent.metadata.appt_id;
                if (appointmentId) {
                    onOpenAppointment(appointmentId);
                }
            }

            setMessages((current) => [
                ...current,
                {
                    id: crypto.randomUUID(),
                    role: "assistant",
                    content: result.answer,
                    facts: result.facts,
                    quickActions: result.quick_actions,
                    actionIntent: result.action_intent,
                },
            ]);
            if (result.suggested_questions.length) {
                setSuggestions(result.suggested_questions);
            }
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "Unable to ask the Global AI Warehouse Copilot.",
            );
        } finally {
            setRequestLoading(false);
        }
    }

    function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        void submitQuestion();
    }

    async function executeAction(message: DisplayMessage) {
        const intent = message.actionIntent;
        if (!intent) return;

        setExecutingMessageId(message.id);
        setError(null);

        try {
            if (intent.action === "book_appointment") {
                const draft = intent.booking_draft;

                if (!intent.confirmation_required || !draft) {
                    return;
                }

                await confirmBookingDraft(
                    draft,
                    message.id,
                );
                return;
            }

            if (intent.action === "filter_appointments") {
                if (intent.metadata.clear === "true") {
                    onClearFilters();
                } else {
                    onApplyFilters({
                        ...activeFilters,
                        riskLevel: intent.metadata.risk_level ?? undefined,
                        status: intent.metadata.status ?? undefined,
                        outcome: undefined,
                    });
                }
                document.querySelector(".operations-workspace-grid")?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
            }

            if (intent.action === "open_appointment") {
                const appointmentId = intent.metadata.appt_id;
                if (appointmentId) onOpenAppointment(appointmentId);
            }

            if (intent.action === "run_what_if") {
                onRunWhatIf({
                    extra_loaders: Number(intent.metadata.extra_loaders ?? 0),
                    extra_forklifts: Number(intent.metadata.extra_forklifts ?? 0),
                    pre_stage_products: intent.metadata.pre_stage_products === "true",
                    facility_id: activeFilters.facilityId,
                });
                document.querySelector(".live-what-if-panel")?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
            }

            setMessages((current) => [
                ...current,
                {
                    id: crypto.randomUUID(),
                    role: "assistant",
                    content: actionConfirmation(intent),
                },
            ]);
        } catch (executionError) {
            setError(
                executionError instanceof Error
                    ? executionError.message
                    : "Unable to execute the Copilot action.",
            );
        } finally {
            setExecutingMessageId(null);
        }
    }

    async function executeQuickAction(action: GlobalCopilotQuickAction) {
        if (action.action === "ask" && action.prompt) {
            await submitQuestion(action.prompt);
            return;
        }

        if (action.action === "filter_appointments") {
            onApplyFilters({
                ...activeFilters,
                facilityId: action.metadata.facility_id ?? activeFilters.facilityId,
                status: action.metadata.status ?? activeFilters.status,
                riskLevel: action.metadata.risk_level ?? activeFilters.riskLevel,
                outcome: action.metadata.outcome ?? activeFilters.outcome,
            });
            document.querySelector(".operations-workspace-grid")?.scrollIntoView({ behavior: "smooth", block: "start" });
            return;
        }

        if (action.action === "open_appointment") {
            const appointmentId = action.metadata.appt_id;
            if (appointmentId) onOpenAppointment(appointmentId);
            return;
        }

        if (action.action === "run_what_if") {
            onRunWhatIf({
                extra_loaders: Number(action.metadata.extra_loaders ?? 0),
                extra_forklifts: Number(action.metadata.extra_forklifts ?? 0),
                pre_stage_products: action.metadata.pre_stage_products === "true",
                facility_id: action.metadata.facility_id ?? activeFilters.facilityId,
            });
            document.querySelector(".live-what-if-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    function updateBookingDraftMessage(
        messageId: string,
        draft: GlobalCopilotBookingDraft,
    ) {
        setBookingDraft(draft);
        setMessages((current) =>
            current.map((message) =>
                message.id === messageId && message.actionIntent
                    ? {
                        ...message,
                        actionIntent: {
                            ...message.actionIntent,
                            booking_draft: draft,
                        },
                    }
                    : message,
            ),
        );
    }

    function clearConversation() {
        setMessages([]);
        setSuggestions(INITIAL_SUGGESTIONS);
        setError(null);
        setBookingDraft(null);
    }

    return (
        <div
            className={`global-copilot-chatbot ${expanded ? "open" : ""}`}
            aria-label="Global AI Warehouse Copilot"
        >
            {expanded && (
                <section className="global-copilot-chat-window">
                    <header className="global-copilot-chat-header">
                        <div className="global-copilot-chat-identity">
                            <div className="global-copilot-chat-avatar" aria-hidden="true">AI</div>
                            <div>
                                <div className="global-copilot-kicker">Global AI Warehouse Copilot</div>
                                <strong>Operations Copilot</strong>
                                <span><i /> Dashboard grounded</span>
                            </div>
                        </div>

                        <button
                            type="button"
                            className="global-copilot-chat-close"
                            onClick={() => setExpanded(false)}
                            aria-label="Close Global AI Warehouse Copilot"
                        >
                            ×
                        </button>
                    </header>

                    <div className="global-copilot-chat-brief">
                        {operationalBrief}
                    </div>

                    <div className="global-copilot-conversation" ref={conversationRef}>
                        {messages.length === 0 && !requestLoading && (
                            <div className="global-copilot-empty-state">
                                <strong>How can I help with warehouse operations?</strong>
                                <span>
                                    Ask about performance, appointments, risks, recommendations,
                                    or book an appointment in natural language.
                                </span>
                            </div>
                        )}

                        {messages.map((message) => (
                            <article key={message.id} className={`global-copilot-message ${message.role}`}>
                                <span className="global-copilot-message-role">
                                    {message.role === "user" ? "You" : "Warehouse Copilot"}
                                </span>
                                <p>{message.content}</p>

                                {!!message.facts?.length && (
                                    <div className="global-copilot-facts">
                                        {message.facts.map((fact) => (
                                            <div key={`${message.id}-${fact.label}`}>
                                                <span>{fact.label}</span>
                                                <strong>{fact.value}</strong>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {!!message.quickActions?.length && (
                                    <div className="global-copilot-quick-actions" aria-label="Suggested Copilot actions">
                                        {message.quickActions.map((action, index) => (
                                            <button
                                                key={`${message.id}-${action.label}-${index}`}
                                                type="button"
                                                onClick={() => void executeQuickAction(action)}
                                                disabled={requestLoading || executingMessageId !== null}
                                            >
                                                {action.label}
                                            </button>
                                        ))}
                                    </div>
                                )}

                                {message.actionIntent?.action === "book_appointment" ? (
                                    <BookingCard
                                        intent={message.actionIntent}
                                        executing={executingMessageId === message.id}
                                        referenceData={referenceData}
                                        onDraftChange={(draft) =>
                                            updateBookingDraftMessage(message.id, draft)
                                        }
                                        onConfirm={() => void executeAction({
                                            ...message,
                                            actionIntent: {
                                                ...message.actionIntent!,
                                                booking_draft:
                                                    bookingDraft ??
                                                    message.actionIntent!.booking_draft,
                                            },
                                        })}
                                    />
                                ) : message.actionIntent ? (
                                    <div className="global-copilot-action-card">
                                        <div>
                                            <span>Prepared dashboard action</span>
                                            <strong>{actionTitle(message.actionIntent)}</strong>
                                        </div>
                                        <button
                                            type="button"
                                            onClick={() => void executeAction(message)}
                                            disabled={executingMessageId !== null}
                                        >
                                            {executingMessageId === message.id
                                                ? "Applying…"
                                                : actionButtonLabel(message.actionIntent)}
                                        </button>
                                    </div>
                                ) : null}
                            </article>
                        ))}

                        {requestLoading && (
                            <div
                                className="global-copilot-message assistant typing"
                                aria-label="Copilot is thinking"
                            >
                                <div className="global-copilot-typing">
                                    <span />
                                    <span />
                                    <span />
                                </div>
                            </div>
                        )}
                    </div>

                    {error && (
                        <div className="global-copilot-error">
                            <span>{error}</span>
                            <button type="button" onClick={() => setError(null)}>Dismiss</button>
                        </div>
                    )}

                    <div className="global-copilot-chat-suggestions">
                        {suggestions.slice(0, 3).map((suggestion) => (
                            <button
                                key={suggestion}
                                type="button"
                                onClick={() => void submitQuestion(suggestion)}
                                disabled={requestLoading}
                            >
                                {suggestion}
                            </button>
                        ))}
                    </div>

                    <form className="global-copilot-input-row" onSubmit={handleSubmit}>
                        <input
                            value={question}
                            onChange={(event) => setQuestion(event.target.value)}
                            placeholder="Ask Copilot…"
                            aria-label="Ask the Global AI Warehouse Copilot"
                            disabled={requestLoading}
                            autoFocus
                        />
                        <button
                            type="submit"
                            className="global-copilot-ask"
                            disabled={!question.trim() || requestLoading}
                            aria-label="Send message"
                        >
                            {requestLoading ? "…" : "→"}
                        </button>
                    </form>

                    <footer className="global-copilot-chat-footer">
                        <span>Grounded in dashboard data</span>
                        {messages.length > 0 && (
                            <button type="button" onClick={clearConversation}>Clear chat</button>
                        )}
                    </footer>
                </section>
            )}

            <button
                type="button"
                className="global-copilot-fab"
                onClick={() => setExpanded((current) => !current)}
                aria-label={expanded ? "Close Global AI Warehouse Copilot" : "Open Global AI Warehouse Copilot"}
                aria-expanded={expanded}
            >
                <span className="global-copilot-fab-icon" aria-hidden="true">
                    {expanded ? "×" : "AI"}
                </span>
                {!expanded && <span className="global-copilot-fab-status" aria-hidden="true" />}
            </button>
        </div>
    );
}


function BookingCard({
    intent,
    executing,
    referenceData,
    onDraftChange,
    onConfirm,
}: {
    intent: GlobalCopilotActionIntent;
    executing: boolean;
    referenceData: AppointmentReferenceData | null;
    onDraftChange: (draft: GlobalCopilotBookingDraft) => void;
    onConfirm: () => void;
}) {
    const draft = intent.booking_draft;
    const [newProductId, setNewProductId] = useState("");
    const [newProductQuantity, setNewProductQuantity] = useState(1);

    if (!draft) return null;

    // Capture the narrowed draft in a non-null local so nested handlers retain
    // the type guard under strict TypeScript / verbatimModuleSyntax builds.
    const bookingDraft: GlobalCopilotBookingDraft = draft;

    const isEditable = intent.confirmation_required;
    const facilityDocks = referenceData?.docks.filter(
        (dock) =>
            !bookingDraft.facility_id ||
            dock.facility_id === bookingDraft.facility_id,
    ) ?? [];

    function updateDraft(
        changes: Partial<GlobalCopilotBookingDraft>,
    ) {
        onDraftChange({
            ...bookingDraft,
            ...changes,
            // Partial<T> permits undefined for required properties. Preserve
            // existing required booking values unless a concrete replacement
            // was supplied.
            load_type: changes.load_type ?? bookingDraft.load_type,
            priority: changes.priority ?? bookingDraft.priority,
            sla_minutes: changes.sla_minutes ?? bookingDraft.sla_minutes,
            detention_cost_per_hour:
                changes.detention_cost_per_hour ??
                bookingDraft.detention_cost_per_hour,
            products: changes.products ?? bookingDraft.products,
        });
    }

    function updateReference(
        field: "customer" | "carrier" | "facility" | "dock",
        id: string,
    ) {
        const rows = field === "dock"
            ? facilityDocks
            : referenceData?.[`${field}s` as "customers" | "carriers" | "facilities"] ?? [];
        const match = rows.find((row) => row.id === id);

        if (field === "customer") {
            updateDraft({
                customer_id: id || null,
                customer_label: match?.label ?? null,
            });
        } else if (field === "carrier") {
            updateDraft({
                carrier_id: id || null,
                carrier_label: match?.label ?? null,
            });
        } else if (field === "facility") {
            updateDraft({
                facility_id: id || null,
                facility_label: match?.label ?? null,
                assigned_dock_id: null,
                assigned_dock_label: null,
            });
        } else {
            updateDraft({
                assigned_dock_id: id || null,
                assigned_dock_label: match?.label ?? null,
            });
        }
    }

    function updateProductQuantity(productId: string, quantity: number) {
        updateDraft({
            products: bookingDraft.products.map((product) =>
                product.product_id === productId
                    ? { ...product, quantity: Math.max(1, quantity) }
                    : product,
            ),
        });
    }

    function removeProduct(productId: string) {
        updateDraft({
            products: bookingDraft.products.filter(
                (product) => product.product_id !== productId,
            ),
        });
    }

    function addProduct() {
        if (!newProductId || !referenceData) return;
        const reference = referenceData.products.find(
            (product) => product.id === newProductId,
        );
        if (!reference) return;

        const existing = bookingDraft.products.find(
            (product) => product.product_id === newProductId,
        );
        const products = existing
            ? bookingDraft.products.map((product) =>
                product.product_id === newProductId
                    ? { ...product, quantity: Math.max(1, newProductQuantity) }
                    : product,
            )
            : [
                ...bookingDraft.products,
                {
                    product_id: reference.id,
                    product_label: reference.label,
                    sku: reference.sku,
                    quantity: Math.max(1, newProductQuantity),
                },
            ];

        updateDraft({ products });
        setNewProductId("");
        setNewProductQuantity(1);
    }

    const scheduledLocalValue = bookingDraft.scheduled_time
        ? toDateTimeLocalValue(bookingDraft.scheduled_time)
        : "";

    return (
        <div className="global-copilot-booking-card">
            <div className="global-copilot-booking-header">
                <div>
                    <span>
                        {intent.confirmation_required
                            ? "Pending appointment booking"
                            : "Booking draft"}
                    </span>
                    <strong>
                        {intent.confirmation_required
                            ? "Review and edit before confirmation"
                            : "Copilot is collecting booking details"}
                    </strong>
                </div>
                <span className={intent.confirmation_required ? "ready" : "collecting"}>
                    {intent.confirmation_required ? "Editable" : "In progress"}
                </span>
            </div>

            {isEditable ? (
                <div className="global-copilot-booking-editor">
                    <label>
                        <span>Customer</span>
                        <select
                            value={bookingDraft.customer_id ?? ""}
                            onChange={(event) => updateReference("customer", event.target.value)}
                        >
                            <option value="">Select customer</option>
                            {referenceData?.customers.map((item) => (
                                <option key={item.id} value={item.id}>{item.label}</option>
                            ))}
                        </select>
                    </label>

                    <label>
                        <span>Carrier</span>
                        <select
                            value={bookingDraft.carrier_id ?? ""}
                            onChange={(event) => updateReference("carrier", event.target.value)}
                        >
                            <option value="">Select carrier</option>
                            {referenceData?.carriers.map((item) => (
                                <option key={item.id} value={item.id}>{item.label}</option>
                            ))}
                        </select>
                    </label>

                    <label>
                        <span>Facility</span>
                        <select
                            value={bookingDraft.facility_id ?? ""}
                            onChange={(event) => updateReference("facility", event.target.value)}
                        >
                            <option value="">Select facility</option>
                            {referenceData?.facilities.map((item) => (
                                <option key={item.id} value={item.id}>{item.label}</option>
                            ))}
                        </select>
                    </label>

                    <label>
                        <span>Dock</span>
                        <select
                            value={bookingDraft.assigned_dock_id ?? ""}
                            onChange={(event) => updateReference("dock", event.target.value)}
                        >
                            <option value="">Unassigned</option>
                            {facilityDocks.map((item) => (
                                <option key={item.id} value={item.id}>{item.label}</option>
                            ))}
                        </select>
                    </label>

                    <label>
                        <span>Scheduled</span>
                        <input
                            type="datetime-local"
                            value={scheduledLocalValue}
                            onChange={(event) => updateDraft({
                                scheduled_time: event.target.value
                                    ? new Date(event.target.value).toISOString()
                                    : null,
                            })}
                        />
                    </label>

                    <label>
                        <span>Appointment type</span>
                        <select
                            value={bookingDraft.appointment_type ?? ""}
                            onChange={(event) => updateDraft({
                                appointment_type: event.target.value
                                    ? event.target.value as "Inbound" | "Outbound"
                                    : null,
                            })}
                        >
                            <option value="">Select appointment type</option>
                            <option value="Inbound">Inbound</option>
                            <option value="Outbound">Outbound</option>
                        </select>
                    </label>

                    <label>
                        <span>Load type</span>
                        <select
                            value={bookingDraft.load_type}
                            onChange={(event) => updateDraft({ load_type: event.target.value })}
                        >
                            <option value="Palletized">Palletized</option>
                            <option value="Floor Loaded">Floor Loaded</option>
                            <option value="Full Truckload">Full Truckload</option>
                            <option value="LTL">LTL</option>
                        </select>
                    </label>

                    <label>
                        <span>Priority</span>
                        <input
                            type="number"
                            min={1}
                            max={5}
                            value={bookingDraft.priority}
                            onChange={(event) => updateDraft({ priority: Number(event.target.value) })}
                        />
                    </label>

                    <label>
                        <span>Target SLA (minutes)</span>
                        <input
                            type="number"
                            min={15}
                            max={1440}
                            value={bookingDraft.sla_minutes}
                            onChange={(event) => updateDraft({ sla_minutes: Number(event.target.value) })}
                        />
                    </label>

                    <label>
                        <span>Detention cost/hour</span>
                        <input
                            type="number"
                            min={0}
                            step="0.01"
                            value={bookingDraft.detention_cost_per_hour}
                            onChange={(event) => updateDraft({
                                detention_cost_per_hour: Number(event.target.value),
                            })}
                        />
                    </label>
                </div>
            ) : (
                <div className="global-copilot-booking-grid">
                    <BookingValue label="Customer" value={draft.customer_label} />
                    <BookingValue label="Carrier" value={draft.carrier_label} />
                    <BookingValue label="Facility" value={draft.facility_label} />
                    <BookingValue label="Dock" value={draft.assigned_dock_label ?? "Unassigned"} />
                    <BookingValue
                        label="Scheduled"
                        value={bookingDraft.scheduled_time
                            ? new Date(bookingDraft.scheduled_time).toLocaleString("en-US", {
                                dateStyle: "medium",
                                timeStyle: "short",
                            })
                            : "Not provided"}
                    />
                    <BookingValue
                        label="Appointment type"
                        value={bookingDraft.appointment_type ?? "Not selected"}
                    />
                    <BookingValue label="Load type" value={bookingDraft.load_type} />
                    <BookingValue label="Target SLA" value={`${bookingDraft.sla_minutes} minutes`} />
                    <BookingValue
                        label="Detention cost"
                        value={`$${bookingDraft.detention_cost_per_hour.toLocaleString("en-US")}/hour`}
                    />
                </div>
            )}

            <div className="global-copilot-booking-products">
                <span>Products</span>
                {bookingDraft.products.map((product) => (
                    <div key={product.product_id} className="global-copilot-booking-product-row">
                        <strong>{product.product_label ?? product.product_id}</strong>
                        {isEditable ? (
                            <div>
                                <input
                                    type="number"
                                    min={1}
                                    value={product.quantity}
                                    aria-label={`Quantity for ${product.product_label ?? product.product_id}`}
                                    onChange={(event) => updateProductQuantity(
                                        product.product_id,
                                        Number(event.target.value),
                                    )}
                                />
                                <button
                                    type="button"
                                    onClick={() => removeProduct(product.product_id)}
                                >
                                    Remove
                                </button>
                            </div>
                        ) : (
                            <span>× {product.quantity.toLocaleString()}</span>
                        )}
                    </div>
                ))}

                {isEditable && (
                    <div className="global-copilot-booking-add-product">
                        <select
                            value={newProductId}
                            onChange={(event) => setNewProductId(event.target.value)}
                        >
                            <option value="">Add another product</option>
                            {referenceData?.products.map((product) => (
                                <option key={product.id} value={product.id}>
                                    {product.label} · {product.sku}
                                </option>
                            ))}
                        </select>
                        <input
                            type="number"
                            min={1}
                            value={newProductQuantity}
                            aria-label="New product quantity"
                            onChange={(event) => setNewProductQuantity(Number(event.target.value))}
                        />
                        <button type="button" onClick={addProduct} disabled={!newProductId}>
                            Add
                        </button>
                    </div>
                )}
            </div>

            {intent.confirmation_required && (
                <div className="global-copilot-booking-actions">
                    <button
                        type="button"
                        onClick={onConfirm}
                        disabled={executing}
                    >
                        {executing ? "Booking…" : "Confirm booking"}
                    </button>
                    <span>
                        All fields remain editable until confirmation. No database record is created before you confirm.
                    </span>
                </div>
            )}
        </div>
    );
}

function toDateTimeLocalValue(value: string) {
    const date = new Date(value);
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60_000)
        .toISOString()
        .slice(0, 16);
}

function BookingValue({
    label,
    value,
}: {
    label: string;
    value?: string | null;
}) {
    return (
        <div>
            <span>{label}</span>
            <strong>{value || "Not provided"}</strong>
        </div>
    );
}

function actionTitle(intent: GlobalCopilotActionIntent) {
    if (intent.action === "filter_appointments") return intent.metadata.clear === "true" ? "Clear appointment filters" : "Filter appointment queue";
    if (intent.action === "open_appointment") return `Open ${intent.metadata.appt_id ?? "appointment"}`;
    if (intent.action === "run_what_if") return "Run portfolio What-If simulation";
    if (intent.action === "book_appointment") return "Book appointment";
    return "Apply dashboard action";
}

function actionButtonLabel(intent: GlobalCopilotActionIntent) {
    if (intent.action === "filter_appointments") return intent.metadata.clear === "true" ? "Clear filters" : "Apply filter";
    if (intent.action === "open_appointment") return "Open drawer";
    if (intent.action === "run_what_if") return "Run simulation";
    if (intent.action === "book_appointment") return "Confirm booking";
    return "Apply";
}

function actionConfirmation(intent: GlobalCopilotActionIntent) {
    if (intent.action === "filter_appointments") return intent.metadata.clear === "true" ? "Appointment filters cleared." : "The appointment queue filter is now active.";
    if (intent.action === "open_appointment") return `Opening ${intent.metadata.appt_id}.`;
    if (intent.action === "run_what_if") return "The dashboard What-If simulation is running. Projected values will replace the live baseline when ready.";
    if (intent.action === "book_appointment") return "Appointment booking confirmed.";
    return "Dashboard action applied.";
}
