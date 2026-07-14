from apps.health.repository.health import HealthStatus
from apps.health.service.health import HealthService


class RecordingHealthRepository:
    def __init__(self) -> None:
        self.called = False

    def get_status(self) -> HealthStatus:
        self.called = True
        return "ok"


def test_health_service_delegates_to_repository() -> None:
    repository = RecordingHealthRepository()
    service = HealthService(repository)

    result = service.get_health()

    assert result == "ok"
    assert repository.called is True
