from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from apps.health.router.health import router as health_router
from apps.story_bible.router.story_bible import router as story_bible_router

app = FastAPI(title="Romance Agent API", version="0.1.0")
app.include_router(health_router)
app.include_router(story_bible_router)


@app.exception_handler(RequestValidationError)
async def malformed_request_handler(
    _request: Request,
    _error: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "code": "MALFORMED_REQUEST",
            "message": "요청 형식을 확인해 주세요.",
            "fieldErrors": [],
        },
    )
