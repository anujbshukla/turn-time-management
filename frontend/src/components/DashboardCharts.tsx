import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import type {
    LateAppointmentOutcome,
    RiskDistributionItem,
} from "../types/dashboard";

type DashboardChartsProps = {
    lateOutcomes: LateAppointmentOutcome[];
    riskDistribution: RiskDistributionItem[];
    selectedRiskLevel?: string;
    selectedOutcome?: string;
    onRiskSelect: (riskLevel: string) => void;
    onOutcomeSelect: (outcome: string) => void;
};

const RISK_COLORS: Record<string, string> = {
    Low: "#2f9e6f",
    Medium: "#d9a824",
    High: "#e47b3c",
    Critical: "#c84b45",
};

export function DashboardCharts({
    lateOutcomes,
    riskDistribution,
    selectedRiskLevel,
    selectedOutcome,
    onRiskSelect,
    onOutcomeSelect,
}: DashboardChartsProps) {
    function handleOutcomeClick(data: unknown) {
        const item = data as {
            outcome?: string;
            payload?: {
                outcome?: string;
            };
        };

        const outcome =
            item.outcome ??
            item.payload?.outcome;

        if (typeof outcome === "string") {
            onOutcomeSelect(outcome);
        }
    }

    function handleRiskClick(data: unknown) {
        const item = data as {
            risk_level?: string;
            payload?: {
                risk_level?: string;
            };
        };

        const riskLevel =
            item.risk_level ??
            item.payload?.risk_level;

        if (typeof riskLevel === "string") {
            onRiskSelect(riskLevel);
        }
    } return (
        <section className="dashboard-charts-grid">
            <article className="panel chart-panel">
                <div className="panel-header">
                    <div>
                        <h2>Late Appointment Outcomes</h2>
                        <p>
                            Comparison of recovered and missed late
                            appointments
                        </p>
                    </div>
                </div>

                <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                            data={lateOutcomes}
                            margin={{
                                top: 8,
                                right: 12,
                                left: 0,
                                bottom: 22,
                            }}
                        >
                            <CartesianGrid
                                strokeDasharray="3 3"
                                vertical={false}
                            />

                            <XAxis
                                dataKey="outcome"
                                interval={0}
                                angle={-12}
                                textAnchor="end"
                                height={66}
                                tick={{ fontSize: 11 }}
                            />

                            <YAxis
                                allowDecimals={false}
                                tick={{ fontSize: 11 }}
                            />

                            <Tooltip />

                            <Bar
                                dataKey="appointment_count"
                                name="Appointments"
                                radius={[6, 6, 0, 0]}
                                fill="#3158a5"
                                cursor="pointer"
                                onClick={handleOutcomeClick}
                            >
                                {lateOutcomes.map((item) => (
                                    <Cell
                                        key={item.outcome}
                                        fill={
                                            selectedOutcome === item.outcome
                                                ? "#172033"
                                                : "#3158a5"
                                        }
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </article>

            <article className="panel chart-panel">
                <div className="panel-header">
                    <div>
                        <h2>Risk Distribution</h2>
                        <p>
                            Current appointments by operational risk
                            level
                        </p>
                    </div>
                </div>

                <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={riskDistribution}
                                dataKey="appointment_count"
                                nameKey="risk_level"
                                innerRadius={60}
                                outerRadius={92}
                                paddingAngle={3}
                                cursor="pointer"
                                onClick={handleRiskClick}
                            >
                                {riskDistribution.map((item) => (
                                    <Cell
                                        key={item.risk_level}
                                        fill={
                                            selectedRiskLevel === item.risk_level
                                                ? "#172033"
                                                : RISK_COLORS[item.risk_level] ??
                                                "#7b8597"
                                        }
                                    />
                                ))}
                            </Pie>

                            <Tooltip />
                            <Legend verticalAlign="bottom" />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </article>
        </section>
    );
}