# Equipment Failure Odoo Sync - Code Changes Detail

## Change 1: Scheduler Task 5 - Added Odoo Sync Integration

**File:** `app/core/scheduler.py`  
**Function:** `equipment_failure_monitoring_task()` (lines 298-430)

### Key Addition: Step 3 - Odoo API Sync

**BEFORE (Missing):**
```python
if save_result.get("saved"):
    logger.info(
        "[TASK 5] Equipment failure saved to DB (id=%s)",
        save_result.get("record_id"),
    )
    # NO ODOO SYNC HERE!
    # Function ends, no API call made
```

**AFTER (Fixed):**
```python
if save_result.get("saved"):
    logger.info(
        f"[TASK 5] ✓ Equipment failure saved to DB\n"
        f"  Record ID: {save_result.get('record_id')}\n"
        f"  Equipment: {equipment_code}\n"
        f"  Description: {failure_info}"
    )
    
    # STEP 3: SYNC TO ODOO API (NEW!)
    logger.info("[TASK 5] Step 3: Syncing to Odoo via API...")
    try:
        failure_api_service = await get_equipment_failure_api_service(db)
        failure_date_str = failure_date.strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(
            f"[TASK 5] Calling Odoo API create_failure_report:\n"
            f"  URL: {get_settings().odoo_base_url}/api/scada/failure-report\n"
            f"  Equipment: {equipment_code}\n"
            f"  Description: {failure_info}\n"
            f"  Date: {failure_date_str}"
        )
        
        odoo_result = await failure_api_service.create_failure_report(
            equipment_code=equipment_code,
            description=failure_info,
            date=failure_date_str,
        )
        
        if odoo_result.get("success"):
            logger.info(
                f"[TASK 5] ✓ Odoo sync successful\n"
                f"  Status: {odoo_result.get('status')}\n"
                f"  Message: {odoo_result.get('message')}\n"
                f"  Data: {odoo_result.get('data')}"
            )
        else:
            logger.error(
                f"[TASK 5] ✗ Odoo sync failed\n"
                f"  Status: {odoo_result.get('status')}\n"
                f"  Message: {odoo_result.get('message')}"
            )
    except Exception as odoo_error:
        logger.error(
            f"[TASK 5] ✗ Exception during Odoo sync: {odoo_error}",
            exc_info=True
        )
```

### Added Helper Function

**Location:** `app/core/scheduler.py` (after imports)

```python
async def get_equipment_failure_api_service(db: "Session") -> EquipmentFailureService:
    """Get equipment failure service instance dengan database session."""
    return EquipmentFailureService(db=db)
```

### Added Import

**File:** `app/core/scheduler.py` (line 27)

```python
from app.services.equipment_failure_service import EquipmentFailureService
```

---

## Change 2: Equipment Failure Service - Enhanced Logging

**File:** `app/services/equipment_failure_service.py`

### Method 1: Enhanced `_authenticate()`

**BEFORE:**
```python
async def _authenticate(self) -> Optional[httpx.AsyncClient]:
    """Authenticate dengan Odoo dan return client dengan session cookie."""
    try:
        base_url = self.settings.odoo_base_url.rstrip("/")
        auth_url = f"{base_url}/api/scada/authenticate"
        
        auth_payload = {
            "db": self.settings.odoo_db,
            "login": self.settings.odoo_username,
            "password": self.settings.odoo_password,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(auth_url, json=auth_payload)
            response.raise_for_status()
            
            auth_data = response.json()
            
            # Handle both direct status dan nested result.status
            status = auth_data.get("status")
            if not status:
                result = auth_data.get("result", {})
                status = result.get("status")
            
            if status != "success":
                logger.error(f"Odoo auth failed: {auth_data}")
                return None
            
            # Create new client dengan cookies
            cookies = response.cookies
            new_client = httpx.AsyncClient(timeout=30.0)
            new_client.cookies.update(cookies)
            logger.info(f"✓ Authenticated with Odoo successfully")
            return new_client
    
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None
```

**AFTER (with detailed logging):**
```python
async def _authenticate(self) -> Optional[httpx.AsyncClient]:
    """Authenticate dengan Odoo dan return client dengan session cookie."""
    try:
        base_url = self.settings.odoo_base_url.rstrip("/")
        auth_url = f"{base_url}/api/scada/authenticate"
        
        auth_payload = {
            "db": self.settings.odoo_db,
            "login": self.settings.odoo_username,
            "password": self.settings.odoo_password,
        }
        
        # ADD: Log attempt
        logger.info(f"[Odoo Auth] Attempting authentication at: {auth_url}")
        logger.debug(f"[Odoo Auth] Payload - db: {auth_payload.get('db')}, login: {auth_payload.get('login')}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(auth_url, json=auth_payload)
            
            # ADD: Log response status
            logger.debug(f"[Odoo Auth] Response status: {response.status_code}")
            
            response.raise_for_status()
            
            auth_data = response.json()
            # ADD: Log response data
            logger.debug(f"[Odoo Auth] Response data: {auth_data}")
            
            # Handle both direct status dan nested result.status
            status = auth_data.get("status")
            if not status:
                result = auth_data.get("result", {})
                status = result.get("status")
            
            if status != "success":
                # IMPROVED: Clear error message
                logger.error(f"[Odoo Auth] ✗ Authentication failed: {auth_data}")
                return None
            
            # Create new client dengan cookies
            cookies = response.cookies
            new_client = httpx.AsyncClient(timeout=30.0)
            new_client.cookies.update(cookies)
            # IMPROVED: Clear success message
            logger.info(f"[Odoo Auth] ✓ Successfully authenticated with Odoo (cookies set)")
            # ADD: Log cookies for debugging
            logger.debug(f"[Odoo Auth] Cookies: {dict(new_client.cookies)}")
            return new_client
    
    except httpx.HTTPError as e:
        # NEW: Detailed HTTP error handling
        logger.error(f"[Odoo Auth] ✗ HTTP error during authentication: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"[Odoo Auth] Response status: {e.response.status_code}")
            try:
                logger.error(f"[Odoo Auth] Response body: {e.response.text}")
            except Exception:
                pass
        return None
    except Exception as e:
        # IMPROVED: More detailed error logging
        logger.error(f"[Odoo Auth] ✗ Authentication error: {e}", exc_info=True)
        return None
```

### Method 2: Enhanced `create_failure_report()`

**BEFORE:**
```python
async def create_failure_report(
    self,
    equipment_code: str,
    description: str,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Create equipment failure report di Odoo."""
    try:
        # Authenticate dengan Odoo
        client = await self._authenticate()
        if not client:
            return {
                "success": False,
                "status": "error",
                "message": "Failed to authenticate with Odoo"
            }
        
        # Prepare request payload
        base_url = self.settings.odoo_base_url.rstrip("/")
        api_url = f"{base_url}/api/scada/failure-report"
        
        payload = {
            "equipment_code": equipment_code,
            "description": description,
        }
        
        if date:
            payload["date"] = date
        
        logger.info(f"Creating failure report for equipment: {equipment_code}")
        
        # Send request ke Odoo
        response = await client.post(api_url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("status") == "success":
            logger.info(
                f"✓ Failure report created successfully\n"
                f"  Equipment: {equipment_code}\n"
                f"  Description: {description}\n"
                f"  ID: {result.get('data', {}).get('id')}"
            )

            if self.db:
                self._save_to_db_if_changed(result.get("data", {}))
            
            return {
                "success": True,
                "status": "success",
                "message": result.get("message", "Failure report created"),
                "data": result.get("data", {})
            }
        else:
            error_msg = result.get("message", "Unknown error")
            logger.warning(f"Failure report creation failed: {error_msg}")
            
            return {
                "success": False,
                "status": "error",
                "message": error_msg
            }
    
    except httpx.HTTPError as e:
        error_msg = f"HTTP error: {str(e)}"
        logger.error(f"HTTP error creating failure report: {e}")
        return {
            "success": False,
            "status": "error",
            "message": error_msg
        }
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(f"Error creating failure report: {e}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "message": error_msg
        }
    finally:
        if client:
            await client.aclose()
```

**AFTER (with detailed step-by-step logging):**
```python
async def create_failure_report(
    self,
    equipment_code: str,
    description: str,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Create equipment failure report di Odoo."""
    client = None
    try:
        # ADD: Log entry point
        logger.info(f"[Odoo API] Starting create_failure_report: equipment={equipment_code}, description={description}")
        
        # Authenticate dengan Odoo
        # ADD: Add step indicator
        logger.info(f"[Odoo API] Step 1: Authenticating with Odoo...")
        client = await self._authenticate()
        if not client:
            # IMPROVED: Clear error message
            logger.error(f"[Odoo API] ✗ Authentication failed - cannot proceed")
            return {
                "success": False,
                "status": "error",
                "message": "Failed to authenticate with Odoo"
            }
        
        # Prepare request payload
        base_url = self.settings.odoo_base_url.rstrip("/")
        api_url = f"{base_url}/api/scada/failure-report"
        
        payload = {
            "equipment_code": equipment_code,
            "description": description,
        }
        
        if date:
            payload["date"] = date
        
        # ADD: Detailed request logging
        logger.info(
            f"[Odoo API] Step 2: Sending POST request\n"
            f"  URL: {api_url}\n"
            f"  Payload: {payload}"
        )
        
        # Send request ke Odoo
        response = await client.post(api_url, json=payload)
        
        # ADD: Log response status
        logger.info(f"[Odoo API] Response status code: {response.status_code}")
        
        response.raise_for_status()
        
        result = response.json()
        # ADD: Log response data
        logger.debug(f"[Odoo API] Response JSON: {result}")
        
        if result.get("status") == "success":
            # IMPROVED: More detailed success logging
            logger.info(
                f"[Odoo API] ✓ Failure report created successfully\n"
                f"  Equipment: {equipment_code}\n"
                f"  Description: {description}\n"
                f"  ID: {result.get('data', {}).get('id')}\n"
                f"  Message: {result.get('message')}"
            )

            if self.db:
                self._save_to_db_if_changed(result.get("data", {}))
            
            return {
                "success": True,
                "status": "success",
                "message": result.get("message", "Failure report created"),
                "data": result.get("data", {})
            }
        else:
            error_msg = result.get("message", "Unknown error")
            # IMPROVED: More detailed failure logging
            logger.warning(
                f"[Odoo API] ✗ Failure report creation failed\n"
                f"  Status: {result.get('status')}\n"
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
        # IMPROVED: Detailed HTTP error logging
        logger.error(f"[Odoo API] ✗ HTTP error creating failure report: {e}")
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
        # IMPROVED: More detailed error logging
        logger.error(f"[Odoo API] ✗ Error creating failure report: {e}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "message": error_msg
        }
    finally:
        if client:
            await client.aclose()
            # ADD: Log cleanup
            logger.debug(f"[Odoo API] Client closed")
```

---

## Summary of Changes

### Total Lines Changed
- **app/core/scheduler.py:** ~130 lines added/modified
- **app/services/equipment_failure_service.py:** ~50 lines added/modified

### Key Improvements
1. ✓ Complete Odoo sync pipeline now part of Task 5
2. ✓ 30+ debug logging points added
3. ✓ Step-by-step tracing of data flow
4. ✓ Comprehensive error handling with HTTP response details
5. ✓ Clear success/failure indicators (✓/✗ symbols)
6. ✓ Backward compatible - no breaking changes

### No Breaking Changes
- All existing functionality preserved
- Database schema unchanged
- API endpoints unchanged
- Configuration compatible with existing .env

---

## Testing The Changes

**Before deployment, verify:**

```bash
# 1. Syntax check
python -m py_compile app/core/scheduler.py
python -m py_compile app/services/equipment_failure_service.py

# 2. Start server
python -m uvicorn app.main:app --reload

# 3. Write test data
python test_equipment_failure_write.py

# 4. Watch logs (should see all 3 steps + Odoo sync)
# Search for: [TASK 5] and [Odoo API]

# 5. Verify results
psql $DATABASE_URL -c "SELECT * FROM scada.equipment_failure ORDER BY created_at DESC LIMIT 1;"
psql odoo_db -c "SELECT * FROM scada_failure_report ORDER BY created_at DESC LIMIT 1;"
```

