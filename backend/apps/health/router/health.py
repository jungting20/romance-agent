from typing import Annotated

from fastapi import APIRouter, Depends

from apps.health.repository.health import ProcessHealthRepository
from apps.health.schemas.health import HealthResponse
from apps.health.service.health import HealthService

router = APIRouter(tags=["Health"])


def get_health_service() -> HealthService:
    return HealthService(ProcessHealthRepository())


@router.get("/health", operation_id="getHealth", response_model=HealthResponse)
def get_health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    return HealthResponse(status=service.get_health())
