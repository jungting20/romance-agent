from fastapi import FastAPI

from apps.health.router.health import router as health_router

app = FastAPI(title="Romance Agent API", version="0.1.0")
app.include_router(health_router)
