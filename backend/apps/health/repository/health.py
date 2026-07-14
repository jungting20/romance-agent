from typing import Literal, Protocol

HealthStatus = Literal["ok"]


class HealthRepository(Protocol):
    def get_status(self) -> HealthStatus: ...


class ProcessHealthRepository:
    def get_status(self) -> HealthStatus:
        return "ok"
