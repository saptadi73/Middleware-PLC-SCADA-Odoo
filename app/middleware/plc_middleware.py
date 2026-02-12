from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings


class PLCMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # Placeholder: load mapping config for PLC read/write.
        # Expect PLC mapping values in settings.plc_read_map and settings.plc_write_map.
        _ = settings.plc_read_map
        _ = settings.plc_write_map

        response = await call_next(request)

        # Placeholder: write back to PLC if required based on response or state.
        return response
