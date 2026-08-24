import type {
  AiMission,
  OptimizationMissionScenarioResponse,
  OptimizationScenarioConstraints,
} from "../types/dashboard";

type Props = {
  mission: AiMission;
  scenario: OptimizationScenarioConstraints;
  scenarioResult: OptimizationMissionScenarioResponse | undefined;
  loading: boolean;
  onUpdateScenario: (
    patch: Partial<OptimizationScenarioConstraints>,
  ) => void;
  onRunScenario: () => void | Promise<void>;
};

const RESOURCE_FIELDS = [
  ["max_extra_loaders_per_hour", "Extra loaders / hour"],
  ["max_extra_forklifts_per_hour", "Extra forklifts / hour"],
  ["max_staging_labor_per_hour", "Staging labor / hour"],
] as const;

export function MissionWhatIfPanel({
  mission,
  scenario,
  scenarioResult,
  loading,
  onUpdateScenario,
  onRunScenario,
}: Props) {
  const scenarioMission = scenarioResult?.missions[0];

  return (
    <div className="mission-what-if-panel">
      <div className="mission-what-if-heading">
        <div>
          <span>Mission-level What-If</span>
          <strong>Re-optimize the entire appointment group</strong>
        </div>
        <small>
          Limits are caps on real available headroom, not synthetic capacity.
        </small>
      </div>

      <div className="mission-what-if-controls">
        {RESOURCE_FIELDS.map(([field, label]) => {
          const value = scenario[field];

          return (
            <label key={field}>
              <span>{label}</span>
              <div className="mission-scenario-stepper">
                <button
                  type="button"
                  disabled={(value ?? 0) <= 0}
                  onClick={() =>
                    onUpdateScenario({
                      [field]: Math.max(0, (value ?? 0) - 1),
                    })
                  }
                >
                  −
                </button>
                <strong>{value === null ? "Auto" : value}</strong>
                <button
                  type="button"
                  onClick={() =>
                    onUpdateScenario({
                      [field]: value === null ? 1 : value + 1,
                    })
                  }
                >
                  +
                </button>
                <button
                  type="button"
                  className="quiet"
                  onClick={() => onUpdateScenario({ [field]: null })}
                >
                  Auto
                </button>
              </div>
            </label>
          );
        })}

        <label className="mission-dock-toggle">
          <input
            type="checkbox"
            checked={scenario.allow_dock_reassignment}
            onChange={(event) =>
              onUpdateScenario({
                allow_dock_reassignment: event.target.checked,
              })
            }
          />
          <span>Allow compatible dock reassignment</span>
        </label>
      </div>

      <button
        type="button"
        className="primary"
        disabled={loading}
        onClick={() => void onRunScenario()}
      >
        {loading ? "Re-optimizing..." : "Re-optimize mission"}
      </button>

      {scenarioMission && (
        <div className="mission-scenario-result">
          <div>
            <span>Projected SLA misses</span>
            <strong>
              {mission.projected_sla_misses_before ?? 0}
              {" → "}
              {scenarioMission.projected_sla_misses_after ?? 0}
            </strong>
          </div>
          <div>
            <span>Appointments recovered</span>
            <strong>{scenarioMission.appointments_recovered ?? 0}</strong>
          </div>
          <div>
            <span>Minutes saved</span>
            <strong>
              {Math.round(scenarioMission.projected_minutes_saved)}
            </strong>
          </div>
          <div>
            <span>Net savings</span>
            <strong>
              {formatCurrency(scenarioMission.estimated_financial_benefit)}
            </strong>
          </div>
          <div>
            <span>Dock moves</span>
            <strong>
              {scenarioMission.dock_feasibility?.dock_moves ?? 0}
            </strong>
          </div>
          <div>
            <span>Unresolved shortages</span>
            <strong>
              {scenarioMission.resource_shortages?.length ?? 0}
            </strong>
          </div>
        </div>
      )}
    </div>
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
