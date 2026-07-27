import socket

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.fins_client import FinsUdpClient
from app.services.odoo_auth_service import authenticate_odoo

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {
            "status": "ok",
            "database": "connected",
            "result": result,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={
                "status": "failed",
                "database": "disconnected",
                "error": str(exc),
            },
        ) from exc


@router.get("/health/full")
async def health_full(db: Session = Depends(get_db)):
    settings = get_settings()
    checks: dict[str, dict[str, object]] = {
        "app": {"status": "ok"},
    }

    overall_ok = True

    try:
        db_result = db.execute(text("SELECT 1")).scalar()
        checks["database"] = {
            "status": "ok",
            "database": "connected",
            "result": db_result,
        }
    except Exception as exc:  # noqa: BLE001
        overall_ok = False
        checks["database"] = {
            "status": "failed",
            "database": "disconnected",
            "error": str(exc),
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            result = await authenticate_odoo(client)
        checks["odoo"] = {
            "status": "ok",
            "base_url": settings.odoo_base_url,
            "user": result.get("login") or settings.odoo_username,
            "uid": result.get("uid"),
        }
    except Exception as exc:  # noqa: BLE001
        overall_ok = False
        checks["odoo"] = {
            "status": "failed",
            "base_url": settings.odoo_base_url,
            "error": str(exc),
        }

    try:
        if settings.plc_protocol.lower() == "tcp":
            with socket.create_connection(
                (settings.plc_ip, settings.plc_port),
                timeout=settings.plc_timeout_sec,
            ):
                pass
            checks["plc"] = {
                "status": "ok",
                "protocol": settings.plc_protocol,
                "ip": settings.plc_ip,
                "port": settings.plc_port,
            }
        else:
            with FinsUdpClient(
                ip=settings.plc_ip,
                port=settings.plc_port,
                timeout_sec=settings.plc_timeout_sec,
            ) as client:
                connected = client.is_connected
            checks["plc"] = {
                "status": "ok" if connected else "failed",
                "protocol": settings.plc_protocol,
                "ip": settings.plc_ip,
                "port": settings.plc_port,
                "inferred": True,
                "note": "UDP check verifies local socket readiness, not full PLC response",
            }
            overall_ok = overall_ok and connected
    except Exception as exc:  # noqa: BLE001
        overall_ok = False
        checks["plc"] = {
            "status": "failed",
            "protocol": settings.plc_protocol,
            "ip": settings.plc_ip,
            "port": settings.plc_port,
            "error": str(exc),
        }

    status = "ok" if overall_ok else "degraded"
    return {
        "status": status,
        "checks": checks,
    }
