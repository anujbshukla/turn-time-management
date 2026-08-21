from __future__ import annotations

from .models import CanonicalCopilotQuery
from .semantic_catalog import WarehouseSemanticCatalog


class CanonicalQueryValidator:
    GROUPS = {
        None, "facility", "customer", "carrier", "dock",
        "appointment_type", "status", "product",
    }

    def validate(self, query: CanonicalCopilotQuery) -> CanonicalCopilotQuery:
        if query.domain not in WarehouseSemanticCatalog.DOMAINS:
            raise ValueError(f"Unsupported Copilot domain: {query.domain}")
        if query.metric not in WarehouseSemanticCatalog.METRICS:
            raise ValueError(f"Unsupported Copilot metric: {query.metric}")
        if query.group_by not in self.GROUPS:
            raise ValueError(f"Unsupported Copilot grouping: {query.group_by}")
        unknown = set(query.filters) - set(WarehouseSemanticCatalog.FILTERS)
        if unknown:
            raise ValueError("Unsupported Copilot filters: " + ", ".join(sorted(unknown)))
        if query.explicit_time:
            if query.date_from is None or query.date_to is None:
                raise ValueError("Explicit time expressions require date_from and date_to.")
            if query.date_to <= query.date_from:
                raise ValueError("date_to must be after date_from.")
        query.limit = max(1, min(25, int(query.limit)))
        return query
