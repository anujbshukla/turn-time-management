import type {
  RecommendationData,
} from "../types/dashboard";

interface BestNextActionProps {
  recommendation: RecommendationData;
}

export function BestNextAction({
  recommendation,
}: BestNextActionProps) {
  return (
    <aside className="panel recommendation-panel">
      <div className="recommendation-label">
        Best Next Action
      </div>

      <h2>
        Prioritize {recommendation.appointmentId}
      </h2>

      <p className="recommendation-summary">
        {recommendation.summary}
      </p>

      <div className="action-list">
        <ActionItem
          label="Recommended dock"
          value={recommendation.recommendedDock}
        />

        <ActionItem
          label="Loading sequence"
          value={recommendation.loadingSequence}
        />

        <ActionItem
          label="Additional labor"
          value={recommendation.additionalLabor}
        />

        <ActionItem
          label="Recovery probability"
          value={recommendation.recoveryProbability}
        />

        <ActionItem
          label="Estimated savings"
          value={recommendation.estimatedSavings}
        />
      </div>

      <div className="button-row">
        <button className="primary-button">
          Accept Action
        </button>

        <button className="secondary-button">
          Review
        </button>
      </div>
    </aside>
  );
}

interface ActionItemProps {
  label: string;
  value: string;
}

function ActionItem({
  label,
  value,
}: ActionItemProps) {
  return (
    <div className="action-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}