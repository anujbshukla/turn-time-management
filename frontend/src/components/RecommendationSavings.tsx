import type { RecommendationSavings as RecommendationSavingsData } from "../types/dashboard";

type Props = { savings: RecommendationSavingsData };

function money(value: number) {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
    }).format(value);
}

export function RecommendationSavings({ savings }: Props) {
    return (
        <section className="panel savings-comparison-panel">
            <div className="savings-header">
                <div>
                    <span className="panel-eyebrow">Financial intelligence</span>
                    <h2>Recommendation Savings Comparison</h2>
                    <p>Estimated operating impact with and without accepted recovery recommendations.</p>
                </div>
                <div className="savings-hero-metric">
                    <span>Net savings</span>
                    <strong>{money(savings.net_savings)}</strong>
                    <small>{savings.cost_reduction_percent}% lower operating impact</small>
                </div>
            </div>

            <div className="savings-comparison-grid">
                <div className="comparison-card baseline">
                    <span>Without recommendations</span>
                    <strong>{money(savings.without_recommendations)}</strong>
                    <small>Projected detention exposure</small>
                </div>
                <div className="comparison-arrow" aria-hidden="true">→</div>
                <div className="comparison-card optimized">
                    <span>With recommendations</span>
                    <strong>{money(savings.with_recommendations)}</strong>
                    <small>Exposure plus action cost</small>
                </div>
                <div className="savings-support-metrics">
                    <div><span>Gross savings</span><strong>{money(savings.gross_savings)}</strong></div>
                    <div><span>Action cost</span><strong>{money(savings.action_cost)}</strong></div>
                    <div><span>Recommendation ROI</span><strong>{savings.roi.toFixed(1)}×</strong></div>
                </div>
            </div>
        </section>
    );
}
