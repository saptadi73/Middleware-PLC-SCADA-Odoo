from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.router import router as api_router
from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.middleware.plc_middleware import PLCMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event untuk startup dan shutdown scheduler."""
    # Startup: start scheduler
    start_scheduler()
    yield
    # Shutdown: stop scheduler
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(PLCMiddleware)

app.include_router(api_router)
