import { useEffect, useState } from "react";

import { getDashboard } from "../services/dashboard";

import type {
    DashboardResponse,
} from "../types/dashboard";

export function useDashboard(
    facilityId?: string,
) {
    const [dashboard, setDashboard] =
        useState<DashboardResponse | null>(null);

    const [loading, setLoading] = useState(true);

    const [error, setError] =
        useState<string | null>(null);

    const [refreshKey, setRefreshKey] =
        useState(0);

    useEffect(() => {
        let cancelled = false;

        async function loadDashboard() {
            setLoading(true);
            setError(null);

            try {
                const response =
                    await getDashboard(facilityId);

                if (!cancelled) {
                    setDashboard(response);
                }
            } catch (loadError) {
                if (!cancelled) {
                    setError(
                        loadError instanceof Error
                            ? loadError.message
                            : "Unable to load dashboard",
                    );
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void loadDashboard();

        return () => {
            cancelled = true;
        };
    }, [facilityId, refreshKey]);

    function refresh() {
        setRefreshKey(
            (currentRefreshKey) =>
                currentRefreshKey + 1,
        );
    }

    return {
        dashboard,
        loading,
        error,
        refresh,
    };
}