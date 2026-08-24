import type { RefObject } from "react";
import type {
  AppointmentCopilotResponse,
  CopilotActionIntent,
} from "../types/copilot";
import type { RecommendationAction } from "../types/appointmentDetails";

export type CopilotDisplayMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  facts?: AppointmentCopilotResponse["facts"];
  actionIntent?: CopilotActionIntent | null;
};

type Props = {
  messages: CopilotDisplayMessage[];
  loading: boolean;
  executingActionId: string | null;
  conversationRef: RefObject<HTMLDivElement | null>;
  recommendationActions: RecommendationAction[];
  onConfirmAction: (
    messageId: string,
    intent: CopilotActionIntent,
  ) => void | Promise<void>;
  onCancelAction: (messageId: string) => void;
};

function getActionsForIntent(
  intent: CopilotActionIntent,
  recommendationActions: RecommendationAction[],
) {
  const actionIdSet = new Set(intent.action_ids);

  return recommendationActions.filter((action) =>
    actionIdSet.has(action.recommendation_action_id),
  );
}

export function AppointmentCopilotConversation({
  messages,
  loading,
  executingActionId,
  conversationRef,
  recommendationActions,
  onConfirmAction,
  onCancelAction,
}: Props) {
  return (
    <div
      ref={conversationRef}
      className="copilot-conversation"
    >
      {messages.length === 0 && !loading && (
        <div className="copilot-empty-state">
          <strong>
            Ask about risk, recovery actions, products, SLA, or financial impact.
          </strong>
          <span>
            Copilot answers using this appointment’s live operational data.
          </span>
        </div>
      )}

      {messages.map((message) => {
        const actionIntent = message.actionIntent;
        const confirmationIntent =
          message.role === "assistant" &&
          actionIntent?.confirmation_required &&
          (
            actionIntent.action === "accept_actions" ||
            actionIntent.action === "reject_actions"
          )
            ? actionIntent
            : null;

        const actionsForIntent = confirmationIntent
          ? getActionsForIntent(
              confirmationIntent,
              recommendationActions,
            )
          : [];

        const totalMinutesSaved = actionsForIntent.reduce(
          (total, action) =>
            total + (action.estimated_minutes_saved ?? 0),
          0,
        );

        const totalActionCost = actionsForIntent.reduce(
          (total, action) =>
            total + (action.estimated_action_cost ?? 0),
          0,
        );

        const isAcceptAction =
          confirmationIntent?.action === "accept_actions";

        const allActionIdsResolved =
          confirmationIntent != null &&
          confirmationIntent.action_ids.length > 0 &&
          actionsForIntent.length ===
            confirmationIntent.action_ids.length;

        return (
          <article
            key={message.id}
            className={`copilot-message ${message.role}`}
          >
            <span className="copilot-message-role">
              {message.role === "assistant" ? "Copilot" : "You"}
            </span>

            <p>{message.content}</p>

            {message.facts && message.facts.length > 0 && (
              <div className="copilot-facts">
                {message.facts.map((fact) => (
                  <div key={`${message.id}-${fact.label}`}>
                    <span>{fact.label}</span>
                    <strong>{fact.value}</strong>
                  </div>
                ))}
              </div>
            )}

            {confirmationIntent && (
              <div className="copilot-action-card">
                <div className="copilot-action-card-header">
                  <div>
                    <span className="copilot-action-label">
                      Pending AI action
                    </span>
                    <strong>
                      {isAcceptAction
                        ? "Accept recovery actions"
                        : "Reject recovery actions"}
                    </strong>
                  </div>
                  <span className="copilot-confirmation-badge">
                    Confirmation required
                  </span>
                </div>

                <div className="copilot-action-list">
                  {actionsForIntent.map((action) => (
                    <div
                      key={action.recommendation_action_id}
                      className="copilot-action-list-item"
                    >
                      <div>
                        <strong>{action.action_title}</strong>
                        <span>{action.action_description}</span>
                      </div>

                      <div className="copilot-action-impact">
                        <strong>
                          +{action.estimated_minutes_saved} min
                        </strong>
                        <span>
                          {(action.estimated_action_cost ?? 0).toLocaleString(
                            "en-US",
                            {
                              style: "currency",
                              currency: "USD",
                            },
                          )}
                        </span>
                      </div>
                    </div>
                  ))}

                  {confirmationIntent.action_ids.length === 0 && (
                    <div className="simulation-state">
                      Copilot recognized the command, but could not determine which recovery actions you meant.
                    </div>
                  )}

                  {confirmationIntent.action_ids.length > 0 &&
                    actionsForIntent.length === 0 && (
                      <div className="simulation-state">
                        The proposed action IDs were not found in the current recovery plan.
                      </div>
                    )}

                  {confirmationIntent.action_ids.length > 0 &&
                    actionsForIntent.length > 0 &&
                    !allActionIdsResolved && (
                      <div className="table-error">
                        One or more proposed actions do not belong to the current recovery plan. Confirmation has been disabled.
                      </div>
                    )}
                </div>

                <div className="copilot-action-summary">
                  <div>
                    <span>Selected actions</span>
                    <strong>{actionsForIntent.length}</strong>
                  </div>

                  <div>
                    <span>Estimated recovery</span>
                    <strong>{totalMinutesSaved} min</strong>
                  </div>

                  <div>
                    <span>Estimated cost</span>
                    <strong>
                      {totalActionCost.toLocaleString(
                        "en-US",
                        {
                          style: "currency",
                          currency: "USD",
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
                      executingActionId !== null ||
                      !allActionIdsResolved
                    }
                    onClick={() =>
                      void onConfirmAction(
                        message.id,
                        confirmationIntent,
                      )
                    }
                  >
                    {executingActionId === message.id
                      ? "Applying..."
                      : "Confirm"}
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    disabled={executingActionId !== null}
                    onClick={() => onCancelAction(message.id)}
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
  );
}
