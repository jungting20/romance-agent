from apps.health.repository.health import HealthRepository, HealthStatus


class HealthService:
    def __init__(self, repository: HealthRepository) -> None:
        self._repository = repository

    def get_health(self) -> HealthStatus:
        return self._repository.get_status()
