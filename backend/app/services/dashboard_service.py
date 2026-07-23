from app.repositories.dashboard_repository import (
    DashboardRepository,
)


class DashboardService:
    def __init__(self, repository: DashboardRepository):
        self.repository = repository

    def summary(self):
        return {
            "appointments": self.repository.appointment_count()
        }