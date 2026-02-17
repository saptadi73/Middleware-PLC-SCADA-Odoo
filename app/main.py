from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI

from app.api.routes.router import router as api_router
from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.core.db_logger import DatabaseLogHandler
from app.middleware.plc_middleware import PLCMiddleware

logging.basicConfig(
    level=logging.INFO,  # Set level ke INFO atau DEBUG
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log ke console
    ]
)

# Configure logging untuk reduce APScheduler noise
logging.getLogger("apscheduler.schedulers.base").setLevel(logging.WARNING)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

settings = get_settings()

# --- ADD DATABASE LOGGER ---
# Ini akan menangkap log INFO ke atas dan simpan ke DB
db_handler = DatabaseLogHandler()
db_handler.setLevel(logging.INFO)  # Set ke DEBUG jika ingin semua detail
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
db_handler.setFormatter(formatter)
logging.getLogger().addHandler(db_handler)
# ---------------------------


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
