import { useEffect, useRef, useState } from "react";

import { runWhatIf } from "../services/whatIf";

import type {
    WhatIfRequest,
    WhatIfResponse,
} from "../types/whatIf";

type UseWhatIfOptions = {
    appointmentId?: string;

    selectedActionIds: number[];

    extraLoaders?: number;

    extraForklifts?: number;

    preStageProducts?: boolean;

    enabled?: boolean;

    debounceMilliseconds?: number;
};

export function useWhatIf({
    appointmentId,
    selectedActionIds,
    extraLoaders = 0,
    extraForklifts = 0,
    preStageProducts = false,
    enabled = true,
    debounceMilliseconds = 350,
}: UseWhatIfOptions) {
    const [simulation, setSimulation] =
        useState<WhatIfResponse | null>(null);

    const [loading, setLoading] =
        useState(false);

    const [error, setError] =
        useState<string | null>(null);

    const [refreshKey, setRefreshKey] =
        useState(0);

    const requestSequenceRef = useRef(0);

    const selectedActionKey = [
        ...selectedActionIds,
    ]
        .sort((left, right) => left - right)
        .join(",");

    useEffect(() => {
        if (!appointmentId || !enabled) {
            setSimulation(null);
            setLoading(false);
            setError(null);
            return;
        }

        const requestSequence =
            requestSequenceRef.current + 1;

        requestSequenceRef.current =
            requestSequence;

        const request: WhatIfRequest = {
            selected_action_ids:
                selectedActionKey.length > 0
                    ? selectedActionKey
                        .split(",")
                        .map(Number)
                    : [],

            extra_loaders: extraLoaders,

            extra_forklifts: extraForklifts,

            pre_stage_products:
                preStageProducts,
        };

        const timeoutId = window.setTimeout(
            async () => {
                setLoading(true);
                setError(null);

                try {
                    const response =
                        await runWhatIf(
                            appointmentId,
                            request,
                        );

                    if (
                        requestSequence ===
                        requestSequenceRef.current
                    ) {
                        setSimulation(response);
                    }
                } catch (loadError) {
                    if (
                        requestSequence ===
                        requestSequenceRef.current
                    ) {
                        setSimulation(null);

                        setError(
                            loadError instanceof Error
                                ? loadError.message
                                : "Unable to run What-If analysis",
                        );
                    }
                } finally {
                    if (
                        requestSequence ===
                        requestSequenceRef.current
                    ) {
                        setLoading(false);
                    }
                }
            },
            debounceMilliseconds,
        );

        return () => {
            window.clearTimeout(timeoutId);
        };
    }, [
        appointmentId,
        selectedActionKey,
        extraLoaders,
        extraForklifts,
        preStageProducts,
        enabled,
        debounceMilliseconds,
        refreshKey,
    ]);

    function refresh() {
        setRefreshKey(
            (current) => current + 1,
        );
    }

    function clear() {
        requestSequenceRef.current += 1;
        setSimulation(null);
        setLoading(false);
        setError(null);
    }

    return {
        simulation,
        loading,
        error,
        refresh,
        clear,
    };
}