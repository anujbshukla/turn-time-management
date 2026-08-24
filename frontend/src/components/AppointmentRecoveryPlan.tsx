import type {
  RecommendationAction,
  RecoverySummary,
} from "../types/appointmentDetails";

type Props = {
  actions: RecommendationAction[];
  recovery: RecoverySummary;
  selectedActionIds: Set<number>;
  savingDecision: boolean;
  onToggleAction: (actionId: number) => void;
  onSelectAll: () => void;
  onClearSelection: () => void;
};

function formatDate(
  value: string | null | undefined,
) {
  if (!value) return "—";

  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function actionResourceSummary(
  action: RecommendationAction,
) {
  const resources: string[] = [];

  if (action.additional_loaders > 0) {
    resources.push(
      `${action.additional_loaders} loader${
        action.additional_loaders === 1
          ? ""
          : "s"
      }`,
    );
  }

  if (action.additional_forklifts > 0) {
    resources.push(
      `${action.additional_forklifts} forklift${
        action.additional_forklifts === 1
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
    resources.push(action.required_dock_id);
  }

  return resources.length > 0
    ? resources.join(" · ")
    : "No additional resources";
}

export function AppointmentRecoveryPlan({
  actions,
  recovery,
  selectedActionIds,
  savingDecision,
  onToggleAction,
  onSelectAll,
  onClearSelection,
}: Props) {
  const actionCount = actions.length;

  const allActionsSelected =
    actionCount > 0 &&
    selectedActionIds.size === actionCount;

  return (
    <section className="drawer-section">
      <div className="drawer-section-heading">
        <div>
          <span className="drawer-section-label">
            AI recovery plan
          </span>

          <h3>Warehouse actions</h3>
        </div>

        <div className="minutes-saved">
          <strong>
            {recovery.proposed_minutes_saved ??
              recovery.total_minutes_saved ??
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
                ? onClearSelection
                : onSelectAll
            }
            disabled={savingDecision}
          >
            {allActionsSelected
              ? "Clear all"
              : "Select all"}
          </button>

          <button
            type="button"
            onClick={onClearSelection}
            disabled={
              savingDecision ||
              selectedActionIds.size === 0
            }
          >
            Clear selection
          </button>
        </div>
      )}

      <div className="recovery-action-list">
        {actions.map((action) => {
          const decisionStatus =
            action.decision_status ??
            "Pending";

          return (
            <article
              key={
                action.recommendation_action_id
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
                  disabled={savingDecision}
                  onChange={() =>
                    onToggleAction(
                      action
                        .recommendation_action_id,
                    )
                  }
                  aria-label={`Select ${action.action_title}`}
                />
              </label>

              <div className="action-sequence">
                {action.sequence_number}
              </div>

              <div className="action-content">
                <div className="action-title-row">
                  <h4>
                    {action.action_title}
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
                  {action.action_description}
                </p>

                {action.recommendation_reason && (
                  <p className="action-recommendation-reason">
                    <strong>
                      Why recommended:{" "}
                    </strong>
                    {
                      action.recommendation_reason
                    }
                  </p>
                )}

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
                      {action.decision_by}
                    </span>
                  )}

                  {action.decision_at && (
                    <span>
                      Decision at:{" "}
                      {formatDate(
                        action.decision_at,
                      )}
                    </span>
                  )}
                </div>

                {action.decision_notes && (
                  <p className="decision-notes">
                    {action.decision_notes}
                  </p>
                )}
              </div>
            </article>
          );
        })}

        {actionCount === 0 && (
          <p>
            No structured recovery actions have
            been generated.
          </p>
        )}
      </div>
    </section>
  );
}
