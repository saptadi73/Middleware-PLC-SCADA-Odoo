"""
Equipment Failure Report Service
Membuat dan manage failure report untuk equipment SCADA.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional, List

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.equipment_failure_db_service import EquipmentFailureDbService

logger = logging.getLogger(__name__)


class EquipmentFailureService:
    """Service untuk create dan manage equipment failure report di Odoo."""
    
    def __init__(self, db: Optional[Session] = None):
        self.settings = get_settings()
        self.db = db
    
    async def _authenticate(self) -> Optional[httpx.AsyncClient]:
        """
        Authenticate dengan Odoo dan return client dengan session cookie.
        
        Returns:
            AsyncClient dengan session authenticated, atau None jika gagal
        """
        try:
            base_url = self.settings.odoo_base_url.rstrip("/")
            auth_url = f"{base_url}/api/scada/authenticate"
            
            auth_payload = {
                "db": self.settings.odoo_db,
                "login": self.settings.odoo_username,
                "password": self.settings.odoo_password,
            }
            
            logger.info(f"[Odoo Auth] Attempting authentication at: {auth_url}")
            logger.debug(f"[Odoo Auth] Payload - db: {auth_payload.get('db')}, login: {auth_payload.get('login')}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(auth_url, json=auth_payload)
                
                logger.debug(f"[Odoo Auth] Response status: {response.status_code}")
                
                response.raise_for_status()
                
                auth_data = response.json()
                logger.debug(f"[Odoo Auth] Response data: {auth_data}")
                
                # Handle both direct status dan nested result.status
                status = auth_data.get("status")
                if not status:
                    result = auth_data.get("result", {})
                    status = result.get("status")
                
                if status != "success":
                    logger.error(f"[Odoo Auth] ✗ Authentication failed: {auth_data}")
                    return None
                
                # Create new client dengan cookies
                cookies = response.cookies
                new_client = httpx.AsyncClient(timeout=30.0)
                new_client.cookies.update(cookies)
                logger.info(f"[Odoo Auth] ✓ Successfully authenticated with Odoo (cookies set)")
                logger.debug(f"[Odoo Auth] Cookies: {dict(new_client.cookies)}")
                return new_client
        
        except httpx.HTTPError as e:
            logger.error(f"[Odoo Auth] ✗ HTTP error during authentication: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"[Odoo Auth] Response status: {e.response.status_code}")
                try:
                    logger.error(f"[Odoo Auth] Response body: {e.response.text}")
                except Exception:
                    pass
            return None
        except Exception as e:
            logger.error(f"[Odoo Auth] ✗ Authentication error: {e}", exc_info=True)
            return None
    
    async def create_failure_report(
        self,
        equipment_code: str,
        description: str,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create equipment failure report di Odoo.
        
        Args:
            equipment_code: Equipment code dari scada.equipment
            description: Deskripsi failure
            date: Optional timestamp dalam format YYYY-MM-DD HH:MM:SS atau YYYY-MM-DDTHH:MM
        
        Returns:
            Dict dengan format:
            {
                "success": True/False,
                "status": "success"/"error",
                "message": "...",
                "data": {
                    "id": ...,
                    "equipment_id": ...,
                    "equipment_code": "...",
                    "equipment_name": "...",
                    "description": "...",
                    "date": "2026-02-15T08:30:00"
                }
            }
        """
        client = None
        try:
            logger.info(f"[Odoo API] Starting create_failure_report: equipment={equipment_code}, description={description}")
            
            # Authenticate dengan Odoo
            logger.info(f"[Odoo API] Step 1: Authenticating with Odoo...")
            client = await self._authenticate()
            if not client:
                logger.error(f"[Odoo API] ✗ Authentication failed - cannot proceed")
                return {
                    "success": False,
                    "status": "error",
                    "message": "Failed to authenticate with Odoo"
                }
            
            # Prepare request payload
            base_url = self.settings.odoo_base_url.rstrip("/")
            api_url = f"{base_url}/api/scada/equipment-failure"
            
            payload = {
                "equipment_code": equipment_code,
                "description": description,
            }
            
            if date:
                payload["date"] = date
            
            logger.info(
                f"[Odoo API] Step 2: Sending POST request\n"
                f"  URL: {api_url}\n"
                f"  Payload: {payload}"
            )
            
            # Send request ke Odoo
            response = await client.post(api_url, json=payload)
            
            logger.info(f"[Odoo API] Response status code: {response.status_code}")
            
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"[Odoo API] Response JSON: {result}")
            
            # Handle JSONRPC format - result bisa di top-level atau di dalam "result" key
            # Odoo returns: {"jsonrpc":"2.0", "id":null, "result": {"status":"success", "data":{...}}}
            actual_result = result.get("result", result)
            status = actual_result.get("status")
            message = actual_result.get("message", "Unknown error")
            response_data = actual_result.get("data", {})
            
            if status == "success":
                # Format response data ke struktur standard
                formatted_data = self._format_failure_report_response(response_data)
                
                logger.info(
                    f"[Odoo API] ✓ Equipment failure report created successfully\n"
                    f"  Equipment: {equipment_code}\n"
                    f"  Equipment ID: {formatted_data.get('equipment_id')}\n"
                    f"  Description: {description}\n"
                    f"  ID: {formatted_data.get('id')}\n"
                    f"  Message: {message}"
                )

                if self.db:
                    self._save_to_db_if_changed(response_data)
                
                return {
                    "success": True,
                    "status": "success",
                    "message": message,
                    "data": formatted_data
                }
            else:
                error_msg = message
                logger.warning(
                    f"[Odoo API] ✗ Equipment failure report creation failed\n"
                    f"  Status: {status}\n"
                    f"  Message: {error_msg}\n"
                    f"  Full response: {result}"
                )
                
                return {
                    "success": False,
                    "status": "error",
                    "message": error_msg
                }
        
        except httpx.HTTPError as e:
            error_msg = f"HTTP error: {str(e)}"
            logger.error(f"[Odoo API] ✗ HTTP error creating equipment failure report: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"[Odoo API] Response status: {e.response.status_code}")
                try:
                    logger.error(f"[Odoo API] Response body: {e.response.text}")
                except Exception:
                    pass
            return {
                "success": False,
                "status": "error",
                "message": error_msg
            }
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(f"[Odoo API] ✗ Error creating equipment failure report: {e}", exc_info=True)
            return {
                "success": False,
                "status": "error",
                "message": error_msg
            }
        finally:
            if client:
                await client.aclose()
                logger.debug(f"[Odoo API] Client closed")

    def _format_failure_report_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format Odoo response data ke struktur standard API.
        
        Converts Odoo response format ke format response yang sesuai spek:
        {
            "id": 1,
            "equipment_id": 1,
            "equipment_code": "PLC01",
            "equipment_name": "Main PLC - Injection Machine 01",
            "description": "Motor overload saat proses mixing",
            "date": "2026-02-15T08:30:00"
        }
        """
        # Format date ke ISO 8601 jika perlu
        date_value = data.get("date")
        if isinstance(date_value, str):
            # Jika sudah ISO format, gunakan as-is
            if "T" not in date_value and date_value.count(" ") == 1:
                # Format YYYY-MM-DD HH:MM:SS convert ke ISO
                try:
                    from datetime import datetime
                    dt = datetime.strptime(date_value, "%Y-%m-%d %H:%M:%S")
                    date_value = dt.strftime("%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    pass  # Keep original format
        elif hasattr(date_value, "isoformat"):
            # If it's a datetime object
            date_value = date_value.isoformat()
        
        return {
            "id": data.get("id"),
            "equipment_id": data.get("equipment_id"),
            "equipment_code": data.get("equipment_code"),
            "equipment_name": data.get("equipment_name", ""),
            "description": data.get("description"),
            "date": date_value,
        }

    def _save_to_db_if_changed(self, data: Dict[str, Any]) -> None:
        """Save report to DB only if data changed."""
        if not self.db:
            return

        equipment_code = data.get("equipment_code")
        description = data.get("description")
        date_str = data.get("date")

        if not equipment_code or not description or not date_str:
            return

        try:
            failure_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return

        db_service = EquipmentFailureDbService(self.db)
        db_service.save_if_changed(
            equipment_code=str(equipment_code),
            description=str(description),
            failure_date=failure_date,
            source="api",
        )
    
    async def get_failure_reports(
        self,
        equipment_code: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get failure reports dari Odoo (jika endpoint tersedia).
        
        Args:
            equipment_code: Optional filter by equipment code
            limit: Max records
            offset: Pagination offset
        
        Returns:
            Dict dengan list failure reports
        """
        try:
            client = await self._authenticate()
            if not client:
                return {
                    "success": False,
                    "status": "error",
                    "message": "Failed to authenticate with Odoo"
                }
            
            base_url = self.settings.odoo_base_url.rstrip("/")
            api_url = f"{base_url}/api/scada/failure-reports"
            
            params = {
                "limit": limit,
                "offset": offset,
            }
            
            if equipment_code:
                params["equipment_code"] = equipment_code
            
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("status") == "success":
                logger.info(
                    f"✓ Fetched {len(result.get('data', []))} failure reports"
                )
                
                return {
                    "success": True,
                    "status": "success",
                    "message": "Failure reports fetched successfully",
                    "data": result.get("data", []),
                    "count": result.get("count", 0)
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "message": result.get("message", "Failed to fetch failure reports")
                }
        
        except Exception as e:
            logger.error(f"Error fetching failure reports: {e}")
            return {
                "success": False,
                "status": "error",
                "message": f"Error fetching failure reports: {str(e)}"
            }
        finally:
            if client:
                await client.aclose()


def get_equipment_failure_service(db: Optional[Session] = None) -> EquipmentFailureService:
    """Factory function untuk get equipment failure service instance."""
    return EquipmentFailureService(db=db)
