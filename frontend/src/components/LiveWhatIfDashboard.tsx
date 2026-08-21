import { useEffect, useState } from "react";

import type { DashboardWhatIfResponse } from "../types/dashboard";

type WhatIfRequest = {
    extra_loaders: number;
    extra_forklifts: number;
    pre_stage_products: boolean;
};

type Props = {
    simulation: DashboardWhatIfResponse | null;
    loading: boolean;
    error: string | null;
    initialRequest?: WhatIfRequest | null;
    onRun: (request: WhatIfRequest) => void;
    onReset: () => void;
};

function money(value: number) {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
    }).format(value);
}

function Stepper({
    label,
    value,
    onChange,
}: {
    label: string;
    value: number;
    onChange: (value: number) => void;
}) {
    const decrease = () => onChange(Math.max(0, value - 1));
    const increase = () => onChange(Math.min(5, value + 1));

    return (
        <div className="dashboard-what-if-control-card">
            <div className="dashboard-what-if-control-copy">
                <span>{label}</span>
                <small>Up to 5 additional resources</small>
            </div>

            <div
                className="dashboard-what-if-stepper"
                role="group"
                aria-label={`${label} selector`}
            >
                <button
                    type="button"
                    className="dashboard-what-if-stepper-button"
                    aria-label={`Decrease ${label}`}
                    disabled={value <= 0}
                    onClick={decrease}
                >
                    &minus;
                </button>

                <output className="dashboard-what-if-stepper-value" aria-live="polite">
                    {value}
                </output>

                <button
                    type="button"
                    className="dashboard-what-if-stepper-button"
                    aria-label={`Increase ${label}`}
                    disabled={value >= 5}
                    onClick={increase}
                >
                    &#43;
                </button>
            </div>
        </div>
    );
}

export function LiveWhatIfDashboard({
    simulation,
    loading,
    error,
    initialRequest,
    onRun,
    onReset,
}: Props) {
    const [extraLoaders, setExtraLoaders] = useState(0);
    const [extraForklifts, setExtraForklifts] = useState(0);
    const [preStageProducts, setPreStageProducts] = useState(false);
    useEffect(() => {
        if (!initialRequest) {
            return;
        }

        setExtraLoaders(initialRequest.extra_loaders);
        setExtraForklifts(initialRequest.extra_forklifts);
        setPreStageProducts(initialRequest.pre_stage_products);
    }, [initialRequest]);
    const hasInputs = extraLoaders > 0 || extraForklifts > 0 || preStageProducts;

    function resetAll() {
        setExtraLoaders(0);
        setExtraForklifts(0);
        setPreStageProducts(false);
        onReset();
    }

    function runSimulation() {
        onRun({
            extra_loaders: extraLoaders,
            extra_forklifts: extraForklifts,
            pre_stage_products: preStageProducts,
        });
    }

    return (
        <section className={`panel live-what-if-panel${simulation ? " simulation-active" : ""}`}>
            <div className="what-if-header">
                <div>
                    <span className="panel-eyebrow">Scenario planning</span>
                    <h2>Live What-If Simulation</h2>
                    <p>Model recovery capacity before committing labor, equipment or staging changes.</p>
                </div>

                <span className={`simulation-status-pill ${simulation ? "active" : "idle"}`}>
                    <span aria-hidden="true" />
                    {simulation ? "Simulation active" : "Live baseline"}
                </span>
            </div>

            <div className="dashboard-what-if-layout">
                <div className="dashboard-what-if-controls">
                    <Stepper label="Extra loaders" value={extraLoaders} onChange={setExtraLoaders} />
                    <Stepper label="Extra forklifts" value={extraForklifts} onChange={setExtraForklifts} />

                    <label className={`dashboard-what-if-toggle-card${preStageProducts ? " selected" : ""}`}>
                        <div className="dashboard-what-if-control-copy">
                            <span>Pre-stage products</span>
                            <small>Prioritize complex, high-volume appointments</small>
                        </div>

                        <input
                            type="checkbox"
                            checked={preStageProducts}
                            onChange={(event) => setPreStageProducts(event.target.checked)}
                        />
                        <span className="dashboard-toggle-visual" aria-hidden="true" />
                    </label>

                    <div className="dashboard-what-if-actions">
                        <button
                            type="button"
                            className="dashboard-primary-simulation-button"
                            disabled={!hasInputs || loading}
                            onClick={runSimulation}
                        >
                            {loading ? "Running simulation…" : "Run simulation"}
                        </button>

                        <button
                            type="button"
                            className="dashboard-secondary-simulation-button"
                            onClick={resetAll}
                        >
                            Reset
                        </button>
                    </div>

                    {error && <div className="dashboard-what-if-error">{error}</div>}
                </div>

                <div className="dashboard-what-if-results" aria-live="polite">
                    {simulation ? (
                        <>
                            <div className="simulation-result-grid">
                                <div className="simulation-result-card">
                                    <span>Predicted SLA misses</span>
                                    <div>
                                        <del>{simulation.baseline.predicted_sla_misses}</del>
                                        <strong>{simulation.scenario.predicted_sla_misses}</strong>
                                    </div>
                                    <small>{simulation.scenario.additional_recoveries} additional recoveries</small>
                                </div>

                                <div className="simulation-result-card">
                                    <span>Late turns recovered</span>
                                    <div>
                                        <del>{simulation.baseline.late_turns_recovered}</del>
                                        <strong>{simulation.scenario.late_turns_recovered}</strong>
                                    </div>
                                    <small>{simulation.scenario.appointments_impacted} appointments impacted</small>
                                </div>

                                <div className="simulation-result-card featured">
                                    <span>Net savings</span>
                                    <strong>{money(simulation.scenario.net_savings)}</strong>
                                    <small>{simulation.scenario.total_minutes_saved.toLocaleString()} total minutes saved</small>
                                </div>
                            </div>

                            <div className="simulation-financial-strip">
                                <div>
                                    <span>Gross savings</span>
                                    <strong>{money(simulation.scenario.gross_savings)}</strong>
                                </div>
                                <div>
                                    <span>Action cost</span>
                                    <strong>{money(simulation.scenario.action_cost)}</strong>
                                </div>
                                <div>
                                    <span>Projected exposure</span>
                                    <strong>{money(simulation.scenario.detention_exposure)}</strong>
                                </div>
                            </div>

                            <details className="simulation-assumptions">
                                <summary>Simulation assumptions</summary>
                                <ul>
                                    {simulation.assumptions.map((item) => (
                                        <li key={item}>{item}</li>
                                    ))}
                                </ul>
                            </details>
                        </>
                    ) : (
                        <div className="dashboard-what-if-empty-state">
                            <div className="dashboard-what-if-orbit" aria-hidden="true">
                                <span />
                            </div>
                            <strong>Build a recovery scenario</strong>
                            <p>
                                Adjust available resources, run the simulation and compare projected KPI,
                                chart and financial outcomes with the live baseline.
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
}
