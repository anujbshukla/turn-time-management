import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    LabelList,
    Legend,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

import type { LateAppointmentOutcome, RiskDistributionItem } from "../types/dashboard";

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


function renderOutcomeTick({
    x = 0,
    y = 0,
    payload,
}: {
    x?: number;
    y?: number;
    payload?: { value?: string };
}) {
    const value = String(payload?.value ?? "");
    const lines =
        value === "Recovered with recommendations"
            ? ["Recovered with", "recommendations"]
            : value === "Recovered without recommendations"
                ? ["Recovered without", "recommendations"]
                : [value];

    return (
        <text
            x={x}
            y={y + 14}
            textAnchor="middle"
            fill="#667286"
            fontSize={10}
        >
            {lines.map((line, index) => (
                <tspan key={line} x={x} dy={index === 0 ? 0 : 13}>
                    {line}
                </tspan>
            ))}
        </text>
    );
}

export function DashboardCharts(props: DashboardChartsProps) {
    const totalRisk = props.riskDistribution.reduce((sum, item) => sum + item.appointment_count, 0);

    function handleOutcomeClick(data: unknown) {
        const item = data as { outcome?: string; payload?: { outcome?: string } };
        const outcome = item.outcome ?? item.payload?.outcome;
        if (typeof outcome === "string") props.onOutcomeSelect(outcome);
    }

    function handleRiskClick(data: unknown) {
        const item = data as { risk_level?: string; payload?: { risk_level?: string } };
        const riskLevel = item.risk_level ?? item.payload?.risk_level;
        if (typeof riskLevel === "string") props.onRiskSelect(riskLevel);
    }

    return (
        <section className="dashboard-charts-grid">
            <article className="panel chart-panel">
                <div className="panel-header"><div><h2>Late Appointment Outcomes</h2><p>Comparison of recovered and missed late appointments</p></div></div>
                <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={props.lateOutcomes} margin={{ top: 30, right: 20, left: 16, bottom: 34 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis dataKey="outcome" interval={0} height={72} tick={renderOutcomeTick} />
                            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Bar dataKey="appointment_count" name="Appointments" radius={[8, 8, 0, 0]} fill="#3158a5" cursor="pointer" onClick={handleOutcomeClick} animationDuration={700}>
                                <LabelList dataKey="appointment_count" position="top" className="chart-value-label" />
                                {props.lateOutcomes.map((item) => <Cell key={item.outcome} fill={props.selectedOutcome === item.outcome ? "#172033" : "#3158a5"} />)}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </article>

            <article className="panel chart-panel">
                <div className="panel-header"><div><h2>Risk Distribution</h2><p>Current appointments by operational risk level</p></div></div>
                <div className="chart-container risk-chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={props.riskDistribution}
                                dataKey="appointment_count"
                                nameKey="risk_level"
                                innerRadius={58}
                                outerRadius={92}
                                paddingAngle={3}
                                cursor="pointer"
                                onClick={handleRiskClick}
                                labelLine={false}
                                label={({ name, value }) => {
                                    const count = Number(value ?? 0);
                                    const percent = totalRisk > 0 ? Math.round((count / totalRisk) * 100) : 0;
                                    return `${name}: ${count} (${percent}%)`;
                                }}
                            >
                                {props.riskDistribution.map((item) => <Cell key={item.risk_level} fill={props.selectedRiskLevel === item.risk_level ? "#172033" : RISK_COLORS[item.risk_level] ?? "#7b8597"} />)}
                            </Pie>
                            <Tooltip />
                            <Legend verticalAlign="bottom" />
                        </PieChart>
                    </ResponsiveContainer>
                    <div className="donut-center-label" aria-hidden="true"><strong>{totalRisk.toLocaleString()}</strong><span>Total</span></div>
                </div>
            </article>
        </section>
    );
}
