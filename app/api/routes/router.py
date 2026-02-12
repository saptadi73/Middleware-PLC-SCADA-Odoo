from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.plc import router as plc_router
from app.api.routes.scada import router as scada_router

router = APIRouter()
router.include_router(health_router, prefix="/api")
router.include_router(auth_router, prefix="/api")
router.include_router(scada_router, prefix="/api")
router.include_router(admin_router, prefix="/api")
router.include_router(plc_router, prefix="/api")
