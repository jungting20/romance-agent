from apps.health.repository.health import ProcessHealthRepository


def test_process_health_repository_reports_ok() -> None:
    repository = ProcessHealthRepository()

    assert repository.get_status() == "ok"
