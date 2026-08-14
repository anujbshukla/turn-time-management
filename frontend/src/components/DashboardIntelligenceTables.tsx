import {
    useMemo,
    useState,
} from "react";

import type {
    DelaySlaReasonItem,
    RecoveryPlanPerformanceItem,
} from "../types/dashboard";


type Props = {
    delayReasons: DelaySlaReasonItem[];
    recoveryPlans: RecoveryPlanPerformanceItem[];
};


type DelaySlaReasonsTableProps = {
    delayReasons: DelaySlaReasonItem[];
};


type RecoveryPlanPerformanceTableProps = {
    recoveryPlans: RecoveryPlanPerformanceItem[];
};


type IntelligenceView =
    | "delay-reasons"
    | "recovery-plans";


type RecoverySort =
    | "used"
    | "helpful";


function formatPercent(
    value: number | null,
) {
    return `${Math.round(value ?? 0)}%`;
}


function formatCurrency(
    value: number,
) {
    return new Intl.NumberFormat(
        "en-US",
        {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 0,
        },
    ).format(value);
}


function ProgressMetric({
    value,
}: {
    value: number | null;
}) {
    const safeValue = Math.max(
        0,
        Math.min(
            100,
            value ?? 0,
        ),
    );

    return (
        <div className="inline-progress-metric">
            <div
                className="inline-progress-track"
                aria-hidden="true"
            >
                <span
                    style={{
                        width: `${safeValue}%`,
                    }}
                />
            </div>

            <strong>
                {formatPercent(value)}
            </strong>
        </div>
    );
}


function DelayReasonsTableContent({
    delayReasons,
}: DelaySlaReasonsTableProps) {
    return (
        <div className="intelligence-table-wrapper">
            <table className="intelligence-table">
                <thead>
                    <tr>
                        <th>Cause</th>
                        <th>Late</th>
                        <th>SLA misses</th>
                        <th>Late share</th>
                        <th>Avg. delay</th>
                        <th>
                            Most affected dock
                        </th>
                    </tr>
                </thead>

                <tbody>
                    {delayReasons.map(
                        (item) => (
                            <tr key={item.reason}>
                                <td>
                                    <div className="reason-cell">
                                        <span className="reason-indicator" />

                                        <strong>
                                            {item.reason}
                                        </strong>
                                    </div>
                                </td>

                                <td>
                                    {item.late_appointments
                                        .toLocaleString()}
                                </td>

                                <td>
                                    <span
                                        className={
                                            `count-badge ${item.sla_misses >
                                                0
                                                ? "danger"
                                                : "neutral"
                                            }`
                                        }
                                    >
                                        {item.sla_misses
                                            .toLocaleString()}
                                    </span>
                                </td>

                                <td>
                                    {formatPercent(
                                        item
                                            .late_share_percent,
                                    )}
                                </td>

                                <td>
                                    {Math.round(
                                        item
                                            .average_delay_minutes ??
                                        0,
                                    )}{" "}
                                    min
                                </td>

                                <td>
                                    {item
                                        .most_affected_dock ??
                                        "Unassigned"}
                                </td>
                            </tr>
                        ),
                    )}

                    {delayReasons.length ===
                        0 && (
                            <tr>
                                <td
                                    colSpan={6}
                                    className="empty-intelligence-state"
                                >
                                    No late-arrival or
                                    SLA-miss causes are
                                    available for the current
                                    operating window.
                                </td>
                            </tr>
                        )}
                </tbody>
            </table>
        </div>
    );
}


function RecoveryPlansTableContent({
    recoveryPlans,
    recoverySort,
}: {
    recoveryPlans:
    RecoveryPlanPerformanceItem[];
    recoverySort: RecoverySort;
}) {
    const sortedRecoveryPlans =
        useMemo(() => {
            return [
                ...recoveryPlans,
            ].sort(
                (
                    left,
                    right,
                ) => {
                    if (
                        recoverySort ===
                        "helpful"
                    ) {
                        return (
                            (
                                right
                                    .success_rate ??
                                0
                            ) -
                            (
                                left
                                    .success_rate ??
                                0
                            ) ||
                            right.net_savings -
                            left.net_savings
                        );
                    }

                    return (
                        right.times_used -
                        left.times_used
                    );
                },
            );
        }, [
            recoveryPlans,
            recoverySort,
        ]);

    return (
        <div className="intelligence-table-wrapper">
            <table className="intelligence-table recovery-table">
                <thead>
                    <tr>
                        <th>Recovery plan</th>
                        <th>Used</th>
                        <th>Acceptance</th>
                        <th>Recoveries</th>
                        <th>Success</th>
                        <th>Avg. saved</th>
                        <th>Net savings</th>
                    </tr>
                </thead>

                <tbody>
                    {sortedRecoveryPlans.map(
                        (item) => (
                            <tr
                                key={
                                    item.action_code
                                }
                            >
                                <td>
                                    <strong>
                                        {
                                            item.recovery_plan
                                        }
                                    </strong>

                                    <span className="table-subtext">
                                        {item.action_code
                                            .replaceAll(
                                                "_",
                                                " ",
                                            )}
                                    </span>
                                </td>

                                <td>
                                    {item.times_used
                                        .toLocaleString()}
                                </td>

                                <td>
                                    <ProgressMetric
                                        value={
                                            item
                                                .acceptance_rate
                                        }
                                    />
                                </td>

                                <td>
                                    {item.sla_recoveries
                                        .toLocaleString()}
                                </td>

                                <td>
                                    <ProgressMetric
                                        value={
                                            item
                                                .success_rate
                                        }
                                    />
                                </td>

                                <td>
                                    {Math.round(
                                        item
                                            .average_minutes_saved ??
                                        0,
                                    )}{" "}
                                    min
                                </td>

                                <td className="positive-value">
                                    {formatCurrency(
                                        item.net_savings,
                                    )}
                                </td>
                            </tr>
                        ),
                    )}

                    {sortedRecoveryPlans.length ===
                        0 && (
                            <tr>
                                <td
                                    colSpan={7}
                                    className="empty-intelligence-state"
                                >
                                    Recovery performance will
                                    appear after recommendation
                                    actions are proposed and
                                    completed.
                                </td>
                            </tr>
                        )}
                </tbody>
            </table>
        </div>
    );
}


/*
 * Standalone export retained for compatibility.
 * Use DashboardIntelligenceTables to show the
 * combined switchable experience.
 */
export function DelaySlaReasonsTable({
    delayReasons,
}: DelaySlaReasonsTableProps) {
    return (
        <section className="dashboard-detail-section">
            <article className="panel intelligence-table-panel">
                <div className="panel-header intelligence-panel-header">
                    <div>
                        <span className="panel-eyebrow">
                            Root-cause intelligence
                        </span>

                        <h2>
                            Delay &amp; SLA Miss Reasons
                        </h2>

                        <p>
                            Operational causes ranked by
                            late arrivals and missed
                            service commitments.
                        </p>
                    </div>

                    <span className="data-quality-pill">
                        Live operational data
                    </span>
                </div>

                <DelayReasonsTableContent
                    delayReasons={
                        delayReasons
                    }
                />
            </article>
        </section>
    );
}


/*
 * Standalone export retained for compatibility.
 * Use DashboardIntelligenceTables to show the
 * combined switchable experience.
 */
export function RecoveryPlanPerformanceTable({
    recoveryPlans,
}: RecoveryPlanPerformanceTableProps) {
    const [
        recoverySort,
        setRecoverySort,
    ] = useState<RecoverySort>(
        "used",
    );

    return (
        <section className="dashboard-detail-section">
            <article className="panel intelligence-table-panel">
                <div className="panel-header intelligence-panel-header">
                    <div>
                        <span className="panel-eyebrow">
                            Recovery intelligence
                        </span>

                        <h2>
                            Recovery Plan Performance
                        </h2>

                        <p>
                            Compare action adoption,
                            effectiveness, time saved and
                            financial impact.
                        </p>
                    </div>

                    <div
                        className="table-segmented-control"
                        role="group"
                        aria-label="Recovery plan sorting"
                    >
                        <button
                            type="button"
                            className={
                                recoverySort ===
                                    "used"
                                    ? "active"
                                    : ""
                            }
                            onClick={() =>
                                setRecoverySort(
                                    "used",
                                )
                            }
                        >
                            Most used
                        </button>

                        <button
                            type="button"
                            className={
                                recoverySort ===
                                    "helpful"
                                    ? "active"
                                    : ""
                            }
                            onClick={() =>
                                setRecoverySort(
                                    "helpful",
                                )
                            }
                        >
                            Most helpful
                        </button>
                    </div>
                </div>

                <RecoveryPlansTableContent
                    recoveryPlans={
                        recoveryPlans
                    }
                    recoverySort={
                        recoverySort
                    }
                />
            </article>
        </section>
    );
}


export function DashboardIntelligenceTables({
    delayReasons,
    recoveryPlans,
}: Props) {
    const [
        intelligenceView,
        setIntelligenceView,
    ] = useState<IntelligenceView>(
        "delay-reasons",
    );

    const [
        recoverySort,
        setRecoverySort,
    ] = useState<RecoverySort>(
        "used",
    );

    const showingDelayReasons =
        intelligenceView ===
        "delay-reasons";

    return (
        <section className="dashboard-detail-section">
            <article className="panel intelligence-table-panel combined-intelligence-panel">
                <div className="panel-header intelligence-panel-header combined-intelligence-header">
                    <div className="combined-intelligence-heading">
                        <span className="panel-eyebrow">
                            {showingDelayReasons
                                ? "Root-cause intelligence"
                                : "Recovery intelligence"}
                        </span>

                        <h2>
                            {showingDelayReasons
                                ? "Delay & SLA Miss Reasons"
                                : "Recovery Plan Performance"}
                        </h2>

                        <p>
                            {showingDelayReasons
                                ? "Operational causes ranked by late arrivals and missed service commitments."
                                : "Compare action adoption, effectiveness, time saved and financial impact."}
                        </p>
                    </div>

                    <div className="combined-intelligence-controls">
                        <div
                            className="table-segmented-control intelligence-view-control"
                            role="tablist"
                            aria-label="Operational intelligence table"
                        >
                            <button
                                type="button"
                                role="tab"
                                aria-selected={
                                    showingDelayReasons
                                }
                                className={
                                    showingDelayReasons
                                        ? "active"
                                        : ""
                                }
                                onClick={() =>
                                    setIntelligenceView(
                                        "delay-reasons",
                                    )
                                }
                            >
                                Delay &amp; SLA Reasons
                            </button>

                            <button
                                type="button"
                                role="tab"
                                aria-selected={
                                    !showingDelayReasons
                                }
                                className={
                                    !showingDelayReasons
                                        ? "active"
                                        : ""
                                }
                                onClick={() =>
                                    setIntelligenceView(
                                        "recovery-plans",
                                    )
                                }
                            >
                                Recovery Plans
                            </button>
                        </div>

                        {showingDelayReasons ? (
                            <span className="data-quality-pill">
                                Live operational data
                            </span>
                        ) : (
                            <div
                                className="table-segmented-control recovery-ranking-control"
                                role="group"
                                aria-label="Recovery plan sorting"
                            >
                                <button
                                    type="button"
                                    className={
                                        recoverySort ===
                                            "used"
                                            ? "active"
                                            : ""
                                    }
                                    onClick={() =>
                                        setRecoverySort(
                                            "used",
                                        )
                                    }
                                >
                                    Most used
                                </button>

                                <button
                                    type="button"
                                    className={
                                        recoverySort ===
                                            "helpful"
                                            ? "active"
                                            : ""
                                    }
                                    onClick={() =>
                                        setRecoverySort(
                                            "helpful",
                                        )
                                    }
                                >
                                    Most helpful
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                <div
                    className="intelligence-table-view"
                    role="tabpanel"
                    aria-label={
                        showingDelayReasons
                            ? "Delay and SLA reasons"
                            : "Recovery plan performance"
                    }
                >
                    {showingDelayReasons ? (
                        <DelayReasonsTableContent
                            delayReasons={
                                delayReasons
                            }
                        />
                    ) : (
                        <RecoveryPlansTableContent
                            recoveryPlans={
                                recoveryPlans
                            }
                            recoverySort={
                                recoverySort
                            }
                        />
                    )}
                </div>
            </article>
        </section>
    );
}