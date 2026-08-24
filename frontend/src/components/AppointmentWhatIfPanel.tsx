import type {
  Dispatch,
  SetStateAction,
} from "react";

import type {
  WhatIfResponse,
} from "../types/whatIf";

type Props = {
  simulation: WhatIfResponse | null;
  loading: boolean;
  error: string | null;
  extraLoaders: number;
  setExtraLoaders: Dispatch<
    SetStateAction<number>
  >;
  extraForklifts: number;
  setExtraForklifts: Dispatch<
    SetStateAction<number>
  >;
  preStageProducts: boolean;
  setPreStageProducts: Dispatch<
    SetStateAction<boolean>
  >;
};

function formatPercent(
  value: number | null | undefined,
) {
  if (value == null) return "—";
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

export function AppointmentWhatIfPanel({
  simulation,
  loading,
  error,
  extraLoaders,
  setExtraLoaders,
  extraForklifts,
  setExtraForklifts,
  preStageProducts,
  setPreStageProducts,
}: Props) {
  return (
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

        {simulation && (
          <span
            className={`impact-status ${
              simulation.scenario
                .sla_recovered
                ? "recovered"
                : "at-risk"
            }`}
          >
            {simulation.scenario
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

      {loading && (
        <div className="simulation-state">
          Running operational simulation...
        </div>
      )}

      {error && (
        <div className="table-error">
          {error}
        </div>
      )}

      {!loading &&
        !error &&
        simulation && (
          <>
            <div className="impact-comparison">
              <div className="impact-column">
                <span>
                  Without recovery actions
                </span>

                <strong>
                  {
                    simulation.baseline
                      .predicted_turn_time_minutes
                  }
                  <small> min</small>
                </strong>

                <p>
                  Risk score{" "}
                  {
                    simulation.baseline
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
                  With simulated plan
                </span>

                <strong>
                  {
                    simulation.scenario
                      .projected_turn_time_minutes
                  }
                  <small> min</small>
                </strong>

                <p>
                  {simulation.scenario
                    .sla_recovered
                    ? `${Math.max(
                        0,
                        simulation.baseline
                          .sla_minutes -
                          simulation.scenario
                            .projected_turn_time_minutes,
                      )} minutes within SLA`
                    : `${Math.max(
                        0,
                        simulation.scenario
                          .projected_turn_time_minutes -
                          simulation.baseline
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
                    simulation
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
                    simulation.scenario
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
                    simulation.scenario
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
                    simulation.scenario
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
                    simulation.scenario
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
                    simulation.scenario
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
                    simulation.scenario
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
                    simulation.scenario
                      .net_savings >= 0
                      ? "positive-impact"
                      : "negative-impact"
                  }
                >
                  {formatCurrency(
                    simulation.scenario
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
                    (simulation.scenario
                      .projected_turn_time_minutes /
                      simulation.baseline
                        .sla_minutes) *
                      100,
                  )}
                  %
                </strong>
              </div>

              <div className="sla-progress-track">
                <div
                  className={`sla-progress-fill ${
                    simulation.scenario
                      .sla_recovered
                      ? "recovered"
                      : "at-risk"
                  }`}
                  style={{
                    width: `${Math.min(
                      100,
                      Math.round(
                        (simulation.scenario
                          .projected_turn_time_minutes /
                          simulation.baseline
                            .sla_minutes) *
                          100,
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
                    simulation.baseline
                      .sla_minutes
                  }{" "}
                  min
                </span>
              </div>
            </div>
          </>
        )}

      {!loading &&
        !error &&
        !simulation && (
          <div className="simulation-state">
            Select recovery actions or adjust
            warehouse resources to run a
            simulation.
          </div>
        )}
    </section>
  );
}
