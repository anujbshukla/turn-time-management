import {
  useEffect,
  useRef,
  useState,
} from "react";
import type { FormEvent } from "react";

import type {
  CopilotActionIntent,
  CopilotConversationMessage,
} from "../types/copilot";
import { askAppointmentCopilot } from "../services/copilot";
import { updateRecommendationDecisions } from "../services/recommendations";
import type { RecommendationAction } from "../types/appointmentDetails";

import {
  AppointmentCopilotConversation,
} from "./AppointmentCopilotConversation";
import type {
  CopilotDisplayMessage,
} from "./AppointmentCopilotConversation";

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

const SUGGESTIONS = [
  "Why is this appointment at risk?",
  "Which recovery action has the highest impact?",
  "Can we meet SLA without extra labor?",
  "What is the projected detention savings?",
  "Accept the highest-impact action.",
];

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
  const [question, setQuestion] = useState("");
  const [
    executingActionId,
    setExecutingActionId,
  ] = useState<string | null>(null);
  const [
    actionExecutionError,
    setActionExecutionError,
  ] = useState<string | null>(null);
  const [messages, setMessages] =
    useState<CopilotDisplayMessage[]>([]);
  const conversationRef =
    useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(false);
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
    if (messages.length === 0 && !loading) {
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
          top: conversation.scrollHeight,
          behavior: "smooth",
        });
      });

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

    if (
      !finalQuestion ||
      loading ||
      executingActionId !== null
    ) {
      return;
    }

    const userMessage:
      CopilotDisplayMessage = {
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
            question: finalQuestion,
            what_if: {
              selected_action_ids:
                selectedActionIds,
              extra_loaders: extraLoaders,
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
        CopilotDisplayMessage = {
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
      intent.action === "accept_actions"
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
          action.recommendation_action_id,
      ),
    );

    const executableActionIds =
      intent.action_ids.filter(
        (actionId) =>
          validActionIds.has(actionId),
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
        decisionStatus === "Accepted"
          ? "Confirmed. The selected recovery actions were accepted."
          : "Confirmed. The selected recovery actions were rejected.";

      setMessages((current) =>
        current.map((message) =>
          message.id === messageId
            ? {
                ...message,
                content:
                  `${message.content}\n\n${confirmationText}`,
                actionIntent: null,
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
              actionIntent: null,
            }
          : message,
      ),
    );

    setActionExecutionError(null);
  }

  function clearConversation() {
    setMessages([]);
    setQuestion("");
    setError(null);
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
                executingActionId !== null
              }
              onClick={clearConversation}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="copilot-suggestions">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            disabled={
              loading ||
              executingActionId !== null
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

      <AppointmentCopilotConversation
        messages={messages}
        loading={loading}
        executingActionId={
          executingActionId
        }
        conversationRef={
          conversationRef
        }
        recommendationActions={
          recommendationActions
        }
        onConfirmAction={
          confirmCopilotAction
        }
        onCancelAction={
          cancelCopilotAction
        }
      />

      {error && (
        <div
          className="table-error"
          role="alert"
          aria-live="polite"
        >
          <strong>
            Copilot request failed
          </strong>
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
              setActionExecutionError(
                null,
              )
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
            executingActionId !== null ||
            question.trim().length === 0
          }
        >
          Ask
        </button>
      </form>
    </section>
  );
}
