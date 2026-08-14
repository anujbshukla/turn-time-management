import { useState } from "react";

import { runDashboardWhatIf } from "../services/dashboard";
import type {
    DashboardWhatIfRequest,
    DashboardWhatIfResponse,
} from "../types/dashboard";

export function useDashboardWhatIf() {
    const [simulation, setSimulation] =
        useState<DashboardWhatIfResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function run(request: DashboardWhatIfRequest) {
        setLoading(true);
        setError(null);
        try {
            const response = await runDashboardWhatIf(request);
            setSimulation(response);
            return response;
        } catch (runError) {
            setSimulation(null);
            setError(
                runError instanceof Error
                    ? runError.message
                    : "Unable to run dashboard What-If simulation",
            );
            return null;
        } finally {
            setLoading(false);
        }
    }

    function reset() {
        setSimulation(null);
        setError(null);
    }

    return { simulation, loading, error, run, reset };
}
