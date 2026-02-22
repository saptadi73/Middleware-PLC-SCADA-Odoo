# SCADA Middleware API Specification (Odoo 14)

**IMPLEMENTASI: JSON-RPC over HTTP**

Dokumentasi lengkap untuk JSON-RPC API endpoints yang compatible dengan Vue.js frontend.

## Base URL

```
http(s)://{odoo-host}/api/scada/
```

**Default**: `http://localhost:8069/api/scada/`

## Authentication

### For Vue.js Frontend (Browser-based)

Gunakan session-based authentication via cookies:

```bash
# 1. Login via Odoo session endpoint
curl -X POST http://localhost:8069/web/session/authenticate \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "db": "your_database",
      "login": "admin@example.com",
      "password": "password"
    }
  }' \
  -c cookies.txt

# 2. Use session cookies untuk API calls
curl -X GET http://localhost:8069/api/scada/health \
  -b cookies.txt
```

### For Middleware/API Client

Gunakan endpoint autentikasi khusus middleware untuk mendapatkan session cookie:

```bash
# 1. Authenticate dan simpan cookie
curl -X POST http://localhost:8069/api/scada/authenticate \
  -H "Content-Type: application/json" \
  -d '{"db": "your_database", "login": "admin", "password": "admin"}' \
  -c cookies.txt

# 2. Use session cookies untuk API calls
curl -X POST http://localhost:8069/api/scada/material-consumption \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"equipment_id": "PLC01", "product_id": 123, "quantity": 10.5, ...}'
```

## Response Format

### Success Response

```json
{
  "status": "success",
  "message": "Description of successful operation",
  "data": { },
  "count": 10,
  "timestamp": "2025-02-06T10:30:00"
}
```

### Error Response

```json
{
  "status": "error",
  "message": "Human-readable error description"
}
```

---

## Endpoints Reference

### 1. Health Check (Public)

**Check SCADA Module Status**

```http
GET /api/scada/health
```

**Parameters**: None

**Response**:

```json
{
  "status": "ok",
  "message": "SCADA Module is running",
  "timestamp": "2025-02-06T10:30:00"
}
```

**cURL Example**:
```bash
curl -X GET http://localhost:8069/api/scada/health
```

---

### 2. Get Version (Public)

**Get SCADA Module Version**

```http
GET /api/scada/version
```

**Parameters**: None

**Response**:

```json
{
  "status": "success",
  "version": "1.0.0",
  "name": "SCADA for Odoo"
}
```

**cURL Example**:
```bash
curl -X GET http://localhost:8069/api/scada/version
```

---

### 3. Authenticate Session (Public)

**Create Session for Middleware**

```http
POST /api/scada/authenticate
Content-Type: application/json
```

**Request Body**:

```json
{
  "db": "your_database",
  "login": "admin",
  "password": "admin"
}
```

**Response**:

```json
{
  "status": "success",
  "uid": 1,
  "session_id": "<session_id>",
  "db": "your_database",
  "login": "admin"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/authenticate \
  -H "Content-Type: application/json" \
  -d '{"db": "your_database", "login": "admin", "password": "admin"}' \
  -c cookies.txt
```

---

### 4. Create Material Consumption (Protected)

**Apply Material Consumption to MO**

```http
POST /api/scada/material-consumption
Auth: Session cookie
Content-Type: application/json
```

**Request Body** (gunakan `product_tmpl_id` atau `product_id`):

```json
{
  "equipment_id": "PLC01",
  "product_tmpl_id": 123,
  "quantity": 10.5,
  "timestamp": "2025-02-06T10:30:00",
  "mo_id": "MO/2025/001",
  "batch_number": "BATCH_001",
  "api_request_id": "REQ_12345"
}

Note: `mo_id` is required to apply consumption to MO.
Note: Successful requests update MO raw material moves (`quantity_done`) for the matching product (consumed updates immediately).
Note: SCADA does not store material consumption records.
```

**Response**:

```json
{
  "status": "success",
  "message": "Material consumption applied to MO moves",
  "mo_id": "MO/2025/001",
  "applied_qty": 10.5,
  "move_ids": [456, 457]
}
```

**Error Responses**:

```json
{
  "status": "error",
  "message": "Equipment not found: PLC01"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/material-consumption \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "product_tmpl_id": 123,
    "quantity": 10.5,
    "timestamp": "2025-02-06T10:30:00",
    "mo_id": "MO/2025/001"
  }'
```


### 5. Get Material Consumption (Protected)

**Deprecated: Material Consumption Record**

```http
GET /api/scada/material-consumption/{record_id}
Auth: Session cookie
```

**Parameters**:
- `record_id` (path): Record ID to retrieve

**Response**:

```json
{
  "status": "error",
  "message": "Material consumption records are not stored; use MO components consumption report instead."
}
```

**cURL Example**:
```bash
curl -X GET http://localhost:8069/api/scada/material-consumption/123 \
  -b cookies.txt
```

---

### 6. Validate Material Consumption (Protected)

**Validate Material Consumption Data**

```http
POST /api/scada/material-consumption/validate
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "equipment_id": "PLC01",
  "product_tmpl_id": 123,
  "quantity": 10.5,
  "timestamp": "2025-02-06T10:30:00",
  "mo_id": "MO/2025/001"
}
```

**Response** (Valid):

```json
{
  "status": "success",
  "message": "Validation passed",
  "data": {
    "equipment_id": "PLC01",
    "product_tmpl_id": 123,
    "quantity": 10.5,
    "timestamp": "2025-02-06T10:30:00",
    "mo_id": "MO/2025/001"
  }
}
```

**Response** (Invalid):

```json
{
  "status": "error",
  "message": "Equipment not found: PLC01"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/material-consumption/validate \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "product_tmpl_id": 123,
    "quantity": 10.5,
    "timestamp": "2025-02-06T10:30:00",
    "mo_id": "MO/2025/001"
  }'
```

---

### 7. Get Manufacturing Order List (Protected)

**Retrieve Manufacturing Orders for Equipment**

```http
GET /api/scada/mo-list?equipment_id=PLC01&status=planned&limit=50&offset=0
Auth: Session cookie
```

**Parameters (JSON-RPC `params`)**:
- `equipment_id` (required): Equipment code
- `status` (optional): Filter by status (`draft`, `confirmed`, `planned`, `progress`, `to_close`, `done`)
- `limit` (optional): Max records (default: 50)
- `offset` (optional): Pagination offset (default: 0)

Note: List is based on `mrp.production` with `scada_equipment_id` matching the equipment code.
Note: MO with status `cancel` is always excluded from this endpoint.

**Response**:

```json
{
  "status": "success",
  "count": 10,
  "data": [
    {
      "mo_id": "MO/2025/001",
      "product": "Product Name",
      "quantity": 100.0,
      "produced_qty": 80.0,
      "consumed_qty": 60.0,
      "status": "planned",
      "schedule_start": "2025-02-06T08:00:00",
      "schedule_end": "2025-02-06T16:00:00"
    }
  ],
  "chart_oee_by_equipment": {
    "x_axis": ["SILO A", "SILO B"],
    "y_axis": {
      "qty_finished": [2495.0, 1800.0],
      "yield_percent": [99.8, 98.6],
      "consumption_ratio": [99.856, 100.4]
    }
  },
  "chart_oee_trend": {
    "x_axis": ["2026-02-14", "2026-02-15", "2026-02-16"],
    "y_axis": {
      "yield_percent": [99.2, 99.6, 99.8],
      "consumption_ratio": [100.1, 99.9, 99.856]
    }
  }
}
```

**cURL Example**:
```bash
curl -X GET "http://localhost:8069/api/scada/mo-list?equipment_id=PLC01&limit=50" \
  -b cookies.txt
```

---

### 8. Get Confirmed MO List (Protected)

**Retrieve confirmed Manufacturing Orders (minimal fields)**

```http
POST /api/scada/mo-list-confirmed
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "limit": 50,
    "offset": 0
  }
}
```

Note: This endpoint is JSON-RPC only. Use the `params` object for inputs.

**Response**:

```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "mo_id": "MO/2026/0001",
      "reference": "SO001",
      "schedule": "2026-02-08T08:00:00",
      "product": "Konsentrat Sapi Penggemukan",
      "quantity": 1000.0
    }
  ],
  "chart_oee_avg_by_equipment": {
    "x_axis": ["SILO A", "SILO B"],
    "y_axis": {
      "yield_percent": [99.68, 98.9],
      "consumption_ratio": [99.90, 100.2]
    }
  }
}
```

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo-list-confirmed \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "limit": 50
    }
  }'
```

---

### 9. Get MO Detail (Protected)

**Retrieve Manufacturing Order detail with BoM and components**

```http
POST /api/scada/mo-detail
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "mo_id": "MO/2026/0001"
  }
}
```

**Response**:

```json
{
  "status": "success",
  "data": {
    "mo_id": "MO/2026/0001",
    "reference": "SO001",
    "state": "confirmed",
    "schedule_start": "2026-02-08T08:00:00",
    "schedule_end": "2026-02-08T16:00:00",
    "equipment": {
      "id": 3,
      "code": "PLC01",
      "name": "Main PLC - Injection Machine 01",
      "equipment_type": "plc",
      "manufacturer": "OMRON",
      "model_number": "CP2E-N20DT-D",
      "serial_number": "SN123456",
      "ip_address": "192.168.1.100",
      "port": 502,
      "protocol": "modbus",
      "is_active": true,
      "connection_status": "connected",
      "sync_status": "synced",
      "last_connected": "2026-02-12T19:53:05.547924"
    },
    "product_tmpl_id": 14,
    "product_id": 32,
    "product_name": "Konsentrat Sapi Penggemukan",
    "quantity": 1000.0,
    "produced_qty": 950.0,
    "uom": "kg",
    "bom_id": 2,
    "bom_code": null,
    "bom_components": [
      {
        "product_tmpl_id": 8,
        "product_id": 8,
        "product_name": "Bungkil Inti Sawit",
        "quantity": 400.0,
        "uom": "kg"
      }
    ],
    "components_consumption": [
      {
        "product_tmpl_id": 8,
        "product_id": 8,
        "product_name": "Bungkil Inti Sawit",
        "to_consume": 400.0,
        "reserved": 0.0,
        "consumed": 0.0,
        "uom": "kg",
        "equipment": {
          "id": 4,
          "code": "SILO_A",
          "name": "SILO A",
          "equipment_type": "silo",
          "manufacturer": null,
          "model_number": null,
          "serial_number": null,
          "ip_address": null,
          "port": 0,
          "protocol": "middleware",
          "is_active": true,
          "connection_status": "connected",
          "sync_status": "pending",
          "last_connected": "2026-02-12T21:22:51.937211"
        }
      }
    ]
  }
}
```

**Notes:**
- `components_consumption` values are based on MO raw material stock moves (`to_consume` = planned qty, `reserved` = reserved qty, `consumed` = done qty)
- `produced_qty` is based on MO finished moves (`quantity_done`)
- MO-level `equipment` object contains full SCADA equipment details linked via `scada_equipment_id` on the MO; null if not set
- Each component includes full `equipment` object if linked to SCADA equipment via component move; null otherwise
- Equipment fields include: id, code, name, equipment_type, manufacturer, model_number, serial_number, ip_address, port, protocol, is_active, connection_status, sync_status, last_connected

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo-detail \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "mo_id": "MO/2026/0001"
    }
  }'
```

---

### 10. Get MO List Detailed (Protected)

**Get detailed list of MOs with components, consumption, and equipment info**

```http
POST /api/scada/mo-list-detailed
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "limit": 10,
    "offset": 0
  }
}
```

**Response**: Same structure as `mo-detail` but returns array of MOs with states 'confirmed', 'progress', 'to_close'

```json
{
  "status": "success",
  "count": 7,
  "data": [
    {
      "mo_id": "WH/MO/00001",
      "reference": null,
      "state": "confirmed",
      "schedule_start": "2026-02-12T13:20:48",
      "schedule_end": "2026-02-12T14:20:48",
      "equipment": {
        "id": 1,
        "code": "PLC01",
        "name": "Main PLC - Injection Machine 01",
        "equipment_type": "plc",
        "manufacturer": "OMRON",
        "model_number": "CP2E-N20DT-D",
        "serial_number": "SN123456",
        "ip_address": "192.168.1.100",
        "port": 502,
        "protocol": "modbus",
        "is_active": true,
        "connection_status": "connected",
        "sync_status": "synced",
        "last_connected": "2026-02-12T19:53:05.547924"
      },
      "product_tmpl_id": 3,
      "product_id": 3,
      "product_name": "JF Plus",
      "quantity": 2500.0,
      "produced_qty": 0.0,
      "uom": "kg",
      "bom_id": 1,
      "bom_code": null,
      "bom_components": [
        {
          "product_tmpl_id": 8,
          "product_id": 8,
          "product_name": "Bungkil Inti Sawit",
          "quantity": 400.0,
          "uom": "kg"
        }
      ],
      "components_consumption": [
        {
          "product_tmpl_id": 8,
          "product_id": 8,
          "product_name": "Bungkil Inti Sawit",
          "to_consume": 400.0,
          "reserved": 0.0,
          "consumed": 0.0,
          "uom": "kg",
          "equipment": {
            "id": 4,
            "code": "SILO_A",
            "name": "SILO A",
            "equipment_type": "silo",
            "manufacturer": null,
            "model_number": null,
            "serial_number": null,
            "ip_address": null,
            "port": 0,
            "protocol": "middleware",
            "is_active": true,
            "connection_status": "connected",
            "sync_status": "pending",
            "last_connected": "2026-02-12T21:22:51.937211"
          }
        }
      ]
    }
  ]
}
```

**Notes:**
- Each MO in the list includes full `equipment` object (MO-level equipment), `bom_components` array, and `components_consumption` array
- Each component in `components_consumption` includes full `equipment` object if linked to SCADA equipment via component move; null otherwise
- Equipment fields include: id, code, name, equipment_type, manufacturer, model_number, serial_number, ip_address, port, protocol, is_active, connection_status, sync_status, last_connected
- `to_consume`, `reserved`, and `consumed` quantities are based on raw material stock moves

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo-list-detailed \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "limit": 10,
      "offset": 0
    }
  }'
```

---

### 11. Get MO List Confirmed (Protected)

**Get confirmed MO list with minimal fields and equipment info**

```http
POST /api/scada/mo-list-confirmed
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "limit": 50,
    "offset": 0
  }
}
```

**Response**:

```json
{
  "status": "success",
  "count": 5,
  "data": [
    {
      "mo_id": "MO/2026/0001",
      "reference": null,
      "schedule": "2026-02-12T08:00:00",
      "schedule_end": "2026-02-12T09:00:00",
      "product": "JF Plus",
      "quantity": 2500.0,
      "state": "confirmed",
      "equipment": {
        "id": 1,
        "code": "PLC01",
        "name": "Main PLC - Injection Machine 01",
        "equipment_type": "plc",
        "manufacturer": "OMRON",
        "model_number": "CP2E-N20DT-D",
        "serial_number": null,
        "ip_address": "192.168.1.100",
        "port": 502,
        "protocol": "modbus",
        "is_active": true,
        "connection_status": "connected",
        "sync_status": "pending",
        "last_connected": "2026-02-09T19:53:05.547924"
      }
    }
  ]
}
```

**Notes:**
- `equipment` field contains full SCADA equipment details linked via `scada_equipment_id` on the MO
- Equipment fields include: id, code, name, equipment_type, manufacturer, model_number, serial_number, ip_address, port, protocol, is_active, connection_status, sync_status, last_connected
- Returns only confirmed MOs (state = 'confirmed')

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo-list-confirmed \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "limit": 50,
      "offset": 0
    }
  }'
```

---

### 12. Get MO List for Equipment (Protected)

**Get MO list for specific equipment with equipment details**

```http
GET /api/scada/mo-list?equipment_id=PLC01&limit=50&offset=0
Auth: Session cookie
```

**Parameters:**
- `equipment_id`: Equipment code to filter MOs (required)
- `status`: MO status filter (optional: confirmed, progress, to_close, etc.)
- `limit`: Number of records to return (default: 50)
- `offset`: Number of records to skip (default: 0)

**Response**:

```json
{
  "status": "success",
  "count": 3,
  "data": [
    {
      "mo_id": "MO/2026/0001",
      "product": "JF Plus",
      "quantity": 2500.0,
      "produced_qty": 0.0,
      "consumed_qty": 0.0,
      "status": "confirmed",
      "schedule_start": "2026-02-12T08:00:00",
      "schedule_end": "2026-02-12T09:00:00",
      "equipment": {
        "id": 1,
        "code": "PLC01",
        "name": "Main PLC - Injection Machine 01",
        "equipment_type": "plc",
        "manufacturer": "OMRON",
        "model_number": "CP2E-N20DT-D",
        "serial_number": null,
        "ip_address": "192.168.1.100",
        "port": 502,
        "protocol": "modbus",
        "is_active": true,
        "connection_status": "connected",
        "sync_status": "pending",
        "last_connected": "2026-02-09T19:53:05.547924"
      }
    }
  ]
}
```

**Notes:**
- Filters manufacturing orders by equipment_id; returns only MOs with scada_equipment_id matching the equipment
- `equipment` field contains full SCADA equipment details with all 14 fields
- Equipment fields include: id, code, name, equipment_type, manufacturer, model_number, serial_number, ip_address, port, protocol, is_active, connection_status, sync_status, last_connected
- `produced_qty` = finished goods completed, `consumed_qty` = raw material consumed
- Returns MOs in any status except `cancel` unless filtered by `status`

**Example**:
```bash
curl -X GET "http://localhost:8069/api/scada/mo-list?equipment_id=PLC01&limit=50&offset=0" \
  -b cookies.txt
```

---

### 13. Create MO Weight (Protected)

**Record actual weight and auto-calc target weight from BoM**

```http
POST /api/scada/mo-weight
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "mo_id": "MO/2025/001",
  "weight_actual": 1200.5,
  "timestamp": "2025-02-06T10:30:00",
  "notes": "Weighing after production"
}
```

**Response**:

```json
{
  "status": "success",
  "message": "MO weight recorded successfully",
  "record_id": 10,
  "mo_id": "MO/2025/001",
  "target_weight": 1185.0,
  "weight_actual": 1200.5
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo-weight \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mo_id": "MO/2025/001",
    "weight_actual": 1200.5,
    "timestamp": "2025-02-06T10:30:00"
  }'
```

---

### 14. Get MO Weight (Protected)

**Retrieve MO weight records**

```http
GET /api/scada/mo-weight?mo_id=MO/2025/001&limit=50&offset=0
Auth: Session cookie
```

**Query Parameters**:
- `mo_id` (optional): MO name atau ID
- `limit` (optional): Max records (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response**:

```json
{
  "status": "success",
  "count": 1,
  "data": [
    {
      "id": 10,
      "mo_id": "MO/2025/001",
      "product_id": 123,
      "target_weight": 1185.0,
      "weight_actual": 1200.5,
      "timestamp": "2025-02-06T10:30:00",
      "notes": "Weighing after production"
    }
  ]
}
```

**cURL Example**:
```bash
curl -X GET "http://localhost:8069/api/scada/mo-weight?mo_id=MO/2025/001" \
  -b cookies.txt
```

---

### 15. Acknowledge Manufacturing Order (Protected)

**Confirm Equipment Received MO Data**

```http
POST /api/scada/mo/{mo_id}/acknowledge
Auth: Session cookie
Content-Type: application/json
```

**Parameters**:
- `mo_id` (path): `mrp.production` ID

**Request Body**:

```json
{
  "equipment_id": "PLC01",
  "status": "acknowledged",
  "timestamp": "2025-02-06T08:00:00"
}
```

**Response**:

```json
{
  "status": "success",
  "message": "MO acknowledged successfully",
  "mo_id": "MO/2025/001"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/123/acknowledge \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "status": "acknowledged",
    "timestamp": "2025-02-06T08:00:00"
  }'
```

---

### 16. Update Manufacturing Order Status (Protected)

**Update MO Production Status**

```http
POST /api/scada/mo/{mo_id}/update-status
Auth: Session cookie
Content-Type: application/json
```

**Parameters**:
- `mo_id` (path): `mrp.production` ID

**Request Body**:

```json
{
  "equipment_id": "PLC01",
  "status": "progress",
  "date_start_actual": "2025-02-06T08:00:00",
  "date_end_actual": "2025-02-06T16:00:00",
  "message": "Production started"
}
```

**Response**:

```json
{
  "status": "success",
  "message": "MO status updated successfully",
  "mo_id": "MO/2025/001"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/123/update-status \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "status": "progress",
    "date_start_actual": "2025-02-06T08:00:00"
  }'
```

---

### 17. Mark Manufacturing Order Done (Protected)

**Complete Manufacturing Order**

```http
POST /api/scada/mo/mark-done
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "equipment_id": "PLC01",
  "mo_id": "MO/2025/001",
  "finished_qty": 1000.0,
  "date_end_actual": "2025-02-06T16:00:00",
  "message": "Production completed"
}
```

Note: `mo_id` and `finished_qty` are required to update finished goods quantity.
Note: `finished_qty` must be > 0. The system sets `qty_producing` to `finished_qty` before marking done.
Note: `mo_id` in payload refers to MO name (e.g. `MO/2025/001`).
Note: If `auto_consume` is enabled, `equipment_id` should be provided so material consumption can be applied to MO moves.

**Response**:

```json
{
  "status": "success",
  "message": "Manufacturing order marked as done",
  "mo_id": "MO/2025/001"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/mark-done \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "mo_id": "MO/2025/001",
    "finished_qty": 1000.0,
    "auto_consume": true,
    "date_end_actual": "2025-02-06T16:00:00"
  }'
```

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/mark-done \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "equipment_id": "PLC01",
      "mo_id": "MO/2025/001",
      "finished_qty": 1000.0,
      "auto_consume": true,
      "date_end_actual": "2025-02-06T16:00:00"
    }
  }'
```

---

### 17A. Mark Manufacturing Order Done by Path ID (Protected)

**Complete Manufacturing Order using `mrp.production` ID in URL path**

```http
POST /api/scada/mo/{mo_id}/mark-done
Auth: Session cookie
Content-Type: application/json
```

**Parameters**:
- `mo_id` (path): `mrp.production` ID

**Request Body**:

```json
{
  "equipment_id": "PLC01",
  "finished_qty": 1000.0,
  "date_end_actual": "2025-02-06T16:00:00",
  "message": "Production completed"
}
```

Note: Endpoint ini memakai MO ID dari path, jadi `mo_id` di body tidak wajib.
Note: Behavior mark done sama dengan endpoint payload-based (`/api/scada/mo/mark-done`).

**Response**:

```json
{
  "status": "success",
  "message": "Manufacturing order marked as done",
  "mo_id": "MO/2025/001"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/123/mark-done \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "finished_qty": 1000.0,
    "auto_consume": true,
    "date_end_actual": "2025-02-06T16:00:00"
  }'
```

---

### 18. Update MO with Consumptions by Equipment Code (Protected)

**Update Manufacturing Order quantity dan material consumption berdasarkan Equipment Code SCADA**

```http
POST /api/scada/mo/update-with-consumptions
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "mo_id": "WH/MO/00001",
  "quantity": 2000,
  "silo101": 825,
  "silo102": 600,
  "silo103": 375,
  "silo104": 240.25
}
```

**Field Descriptions**:
- `mo_id` (required): Manufacturing Order name/number (e.g., "WH/MO/00001")
- `quantity` (optional): Update target quantity MO
- Alias quantity yang juga didukung: `product_qty`, `quantity_to_produce`, `qty_to_produce`, `target_produksi`, `target_production`, `qty_producing`
- `{equipment_code}` (optional): Equipment code SCADA (e.g., "silo101", "silo102") dengan nilai consumption quantity

**How it works**:
1. System akan mencari Manufacturing Order berdasarkan `mo_id`
2. Jika quantity (atau alias quantity) diberikan, system akan:
   - re-scale MO menggunakan wizard standar Odoo `change.production.qty`
   - update `product_qty` dan raw/finished moves agar konsisten
   - sinkronkan `qty_producing` ke target terbaru
3. Untuk setiap equipment code yang dikirim (kecuali `mo_id` dan key quantity):
   - System mencari equipment berdasarkan code (e.g., "silo101")
   - Mencari raw material moves yang berelasi dengan equipment tersebut
   - Apply consumption quantity ke moves tersebut
   - Log consumption ke scada.equipment.material

**Validation Rules**:
- Endpoint hanya bisa update MO yang belum `done/cancel`.
- Jika MO sudah `done` atau `cancel`, request akan ditolak.

**Response**:

```json
{
  "status": "success",
  "message": "MO updated successfully",
  "mo_id": "WH/MO/00001",
  "mo_state": "confirmed",
  "updated_quantity": 2000,
  "consumed_items": [
    {
      "equipment_code": "silo101",
      "equipment_name": "SILO A",
      "applied_qty": 825.0,
      "move_ids": [123],
      "products": ["Pollard Angsa"]
    },
    {
      "equipment_code": "silo102",
      "equipment_name": "SILO B",
      "applied_qty": 600.0,
      "move_ids": [124],
      "products": ["Kopra mesh"]
    },
    {
      "equipment_code": "silo103",
      "equipment_name": "SILO C",
      "applied_qty": 375.0,
      "move_ids": [125],
      "products": ["PKE Pellet"]
    }
  ],
  "errors": []
}
```

**Error Response** (if some items failed):

```json
{
  "status": "success",
  "message": "MO updated with some errors",
  "mo_id": "WH/MO/00001",
  "mo_state": "confirmed",
  "updated_quantity": 2000,
  "consumed_items": [...],
  "errors": [
    "silo999: Equipment not found",
    "silo888: No raw material move found for this equipment"
  ]
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/update-with-consumptions \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mo_id": "WH/MO/00001",
    "quantity": 2000,
    "silo101": 825,
    "silo102": 600,
    "silo103": 375,
    "silo104": 240.25,
    "silo105": 50,
    "silo106": 83.50
  }'
```

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/update-with-consumptions \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "mo_id": "WH/MO/00001",
      "quantity": 2000,
      "silo101": 825,
      "silo102": 600,
      "silo103": 375
    }
  }'
```

**Use Case**:
Endpoint ini ideal untuk sistem SCADA yang sudah mengetahui equipment code untuk setiap material/silo dan ingin mengirimkan consumption data dalam satu request tanpa perlu mengetahui product_id atau material_id.

Frontend hanya perlu mengirim:
- MO name
- Target quantity MO (optional, akan re-scale `product_qty` + raw/finished moves)
- Mapping equipment_code → consumption_quantity

System akan otomatis:
- Mencari material yang berelasi dengan equipment tersebut di MO
- Apply consumption ke raw material moves
- Log consumption history

**Prerequisites**:
1. Manufacturing Order harus sudah exist
2. Equipment code harus terdaftar di SCADA Equipment master
3. Raw material moves harus sudah memiliki relasi ke equipment (via `scada_equipment_id` di BoM Line atau Stock Move)

---

### 19. Cancel Manufacturing Order (Protected)

**Cancel Manufacturing Order by `mo_id`**

```http
POST /api/scada/mo/cancel
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "mo_id": "WH/MO/00003"
}
```

**Response (Success)**:

```json
{
  "status": "success",
  "message": "Manufacturing order cancelled successfully",
  "mo_id": "WH/MO/00003",
  "mo_state": "cancel"
}
```

**Response (Already Cancelled)**:

```json
{
  "status": "success",
  "message": "Manufacturing order already cancelled",
  "mo_id": "WH/MO/00003",
  "mo_state": "cancel"
}
```

**Response (Error)**:

```json
{
  "status": "error",
  "message": "Cannot cancel MO \"WH/MO/00003\" in state \"done\""
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/mo/cancel \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "mo_id": "WH/MO/00003"
  }'
```

---

### 20. Get Equipment Status (Protected)

**Retrieve Equipment Connection & Status**

```http
GET /api/scada/equipment/{equipment_code}
Auth: Session cookie
```

**Parameters**:
- `equipment_code` (path): Equipment code (e.g., PLC01)

**Response**:

```json
{
  "status": "success",
  "data": {
    "id": 1,
    "equipment_code": "PLC01",
    "name": "PLC01",
    "connection_status": "connected",
    "is_active": true,
    "last_connected": "2025-02-06T10:30:00"
  }
}
```

**cURL Example**:
```bash
curl -X GET http://localhost:8069/api/scada/equipment/PLC01 \
  -b cookies.txt
```

---

### 19C. Get OEE Detail (Protected)

**Get OEE detail data for frontend (summary + breakdown per silo/perangkat)**

```http
POST /api/scada/oee-detail
Auth: Session cookie
Content-Type: application/json
```

**Request Body (JSON-RPC params)**:

```json
{
  "oee_id": 10,
  "mo_id": "WH/MO/00001",
  "equipment_code": "silo101",
  "date_from": "2026-02-01",
  "date_to": "2026-02-29",
  "limit": 50,
  "offset": 0
}
```

**Response**:

```json
{
  "status": "success",
  "count": 1,
  "data": [
    {
      "oee_id": 10,
      "date_done": "2026-02-16T09:40:00",
      "mo_id": "WH/MO/00001",
      "mo_record_id": 351,
      "equipment": {
        "id": 4,
        "code": "PLC01",
        "name": "Main PLC - Injection Machine 01"
      },
      "product_id": 112,
      "product_name": "JF Plus",
      "qty_planned": 2500.0,
      "qty_finished": 2495.0,
      "variance_finished": -5.0,
      "yield_percent": 99.8,
      "qty_bom_consumption": 2500.0,
      "qty_actual_consumption": 2496.4,
      "variance_consumption": -3.6,
      "consumption_ratio": 99.856,
      "lines": [
        {
          "equipment_id": 11,
          "equipment_code": "silo101",
          "equipment_name": "SILO A",
          "to_consume": 825.0,
          "actual_consumed": 825.25,
          "variance": 0.25,
          "consumption_ratio": 100.03,
          "material_count": 1
        }
      ]
    }
  ],
  "chart_oee_by_equipment": {
    "x_axis": ["SILO A", "SILO B"],
    "y_axis": {
      "qty_finished": [2495.0, 1800.0],
      "yield_percent": [99.8, 98.6],
      "consumption_ratio": [99.856, 100.4]
    }
  },
  "chart_oee_trend": {
    "x_axis": ["2026-02-14", "2026-02-15", "2026-02-16"],
    "y_axis": {
      "yield_percent": [99.2, 99.6, 99.8],
      "consumption_ratio": [100.1, 99.9, 99.856]
    }
  }
}

**Get average OEE report by SCADA equipment list**

```http
POST /api/scada/oee-equipment-avg
Auth: Session cookie
Content-Type: application/json
```

**Request Body (JSON-RPC params)**:

```json
{
  "equipment_code": "silo101",
  "equipment_type": "silo",
  "is_active": true,
  "date_from": "2026-02-01",
  "date_to": "2026-02-29",
  "limit": 100,
  "offset": 0
}
```

**Response**:

```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "equipment": {
        "id": 11,
        "code": "silo101",
        "name": "SILO A",
        "equipment_type": "silo",
        "is_active": true
      },
      "oee_records_count": 12,
      "avg_summary": {
        "qty_planned": 2500.0,
        "qty_finished": 2492.1,
        "variance_finished": -7.9,
        "yield_percent": 99.68,
        "qty_bom_consumption": 2500.0,
        "qty_actual_consumption": 2497.4,
        "variance_consumption": -2.6,
        "consumption_ratio": 99.90
      },
      "avg_consumption_detail": {
        "to_consume": 825.0,
        "actual_consumed": 825.2,
        "variance": 0.2,
        "consumption_ratio": 100.02,
        "material_count": 1.0
      },
      "last_oee_date": "2026-02-16 09:40:00"
    }
  ],
  "chart_oee_avg_by_equipment": {
    "x_axis": ["SILO A", "SILO B"],
    "y_axis": {
      "yield_percent": [99.68, 98.9],
      "consumption_ratio": [99.90, 100.2]
    }
  }
}
```

---

### 19A. Create Equipment Failure Report (Protected)

**Create failure report for SCADA equipment**

```http
POST /api/scada/equipment-failure
Auth: Session cookie
Content-Type: application/json
```

**Request Body (REST format)**:

```json
{
  "equipment_code": "PLC01",
  "description": "Motor overload saat proses mixing",
  "date": "2026-02-15 08:30:00"
}
```

**JSON-RPC Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "equipment_code": "PLC01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15 08:30:00"
  }
}
```

**Response**:

```json
{
  "status": "success",
  "message": "Equipment failure report created",
  "data": {
    "id": 1,
    "equipment_id": 1,
    "equipment_code": "PLC01",
    "equipment_name": "Main PLC - Injection Machine 01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15T08:30:00"
  }
}
```

**cURL Example (REST)**:
```bash
curl -X POST http://localhost:8069/api/scada/equipment-failure \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_code": "PLC01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15 08:30:00"
  }'
```

**cURL Example (JSON-RPC)**:
```bash
curl -X POST http://localhost:8069/api/scada/equipment-failure \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "equipment_code": "PLC01",
      "description": "Motor overload saat proses mixing",
      "date": "2026-02-15 08:30:00"
    }
  }'
```

### 19B. Get Equipment Failure Reports (Protected)

**Get list of equipment failure reports**

```http
GET /api/scada/equipment-failure?equipment_code=PLC01&limit=50&offset=0
Auth: Session cookie
```

Note: Endpoint ini menggunakan method `GET`.
Untuk report frontend berbasis JSON-RPC gunakan endpoint baru `POST /api/scada/equipment-failure-report` (lihat section 19E).

**Query Parameters**:
- `equipment_code` (optional): filter by SCADA equipment code
- `limit` (optional): max records (default 50)
- `offset` (optional): pagination offset (default 0)

**Response**:

```json
{
  "status": "success",
  "count": 1,
  "data": [
    {
      "id": 1,
      "equipment_id": 1,
      "equipment_code": "PLC01",
      "equipment_name": "Main PLC - Injection Machine 01",
      "description": "Motor overload saat proses mixing",
      "date": "2026-02-15T08:30:00",
      "reported_by": "Administrator"
    }
  ]
}
```

**cURL Example (REST)**:
```bash
curl -X GET "http://localhost:8069/api/scada/equipment-failure?equipment_code=PLC01&limit=50" \
  -b cookies.txt
```

**cURL Example (JSON-RPC)**:
```bash
curl -X POST http://localhost:8069/api/scada/equipment-failure-report \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "equipment_code": "PLC01",
      "limit": 50,
      "offset": 0
    }
  }'
```

---

### 19E. Get Equipment Failure Report (Frontend, Protected)

**Get frontend-ready equipment failure report (detail + summary)**

```http
POST /api/scada/equipment-failure-report
Auth: Session cookie
Content-Type: application/json
```

**Request Body (JSON-RPC params)**:

```json
{
  "equipment_code": "PLC01",
  "period": "this_month",
  "date_from": "2026-02-01",
  "date_to": "2026-02-29",
  "limit": 100,
  "offset": 0
}
```

**Field Descriptions**:
- `equipment_code` (optional): filter by equipment code
- `period` (optional): preset periode waktu. Nilai yang didukung:
  - `today`
  - `yesterday`
  - `this_week`
  - `last_7_days`
  - `this_month`
  - `last_month`
  - `this_year`
- `date_from` (optional): tanggal awal (`YYYY-MM-DD` atau `YYYY-MM-DD HH:MM:SS`)
- `date_to` (optional): tanggal akhir (`YYYY-MM-DD` atau `YYYY-MM-DD HH:MM:SS`)
- `limit` (optional): default `100`
- `offset` (optional): default `0`

Catatan:
- Jika `period` dikirim, sistem akan otomatis set rentang tanggal berdasarkan periode tersebut.
- Jika `date_from`/`date_to` juga dikirim, nilai tanggal manual akan diprioritaskan.

**Response**:

```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "id": 10,
      "equipment_id": 1,
      "equipment_code": "PLC01",
      "equipment_name": "Main PLC - Injection Machine 01",
      "description": "Motor overload",
      "date": "2026-02-15T08:30:00",
      "reported_by": "Administrator"
    },
    {
      "id": 9,
      "equipment_id": 1,
      "equipment_code": "PLC01",
      "equipment_name": "Main PLC - Injection Machine 01",
      "description": "Trip breaker",
      "date": "2026-02-12T11:12:00",
      "reported_by": "Administrator"
    }
  ],
  "summary": {
    "total_failures": 7,
    "equipment_count": 2,
    "by_equipment": [
      {
        "equipment_id": 1,
        "equipment_name": "Main PLC - Injection Machine 01",
        "failure_count": 5,
        "last_failure_date": "2026-02-15 08:30:00"
      },
      {
        "equipment_id": 7,
        "equipment_name": "SILO A",
        "failure_count": 2,
        "last_failure_date": "2026-02-10 13:20:00"
      }
    ]
  }
}
```

**cURL Example (JSON-RPC)**:
```bash
curl -X POST http://localhost:8069/api/scada/equipment-failure-report \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "equipment_code": "PLC01",
      "period": "this_month",
      "limit": 100,
      "offset": 0
    }
  }'
```

---

### 20. KPI Product Report (Protected)

**Get KPI SCADA per Product (range tanggal tertentu)**

```http
POST /api/scada/kpi-product-report
Auth: Session cookie
Content-Type: application/json
```

**JSON-RPC Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "product_id": 112,
    "product_tmpl_id": 45,
    "date_from": "2026-02-01",
    "date_to": "2026-02-29",
    "period": "this_month",
    "limit": 100,
    "offset": 0
  }
}
```

**Parameters**:
- `product_id` (optional): filter by `product.product` ID
- `product_tmpl_id` (optional): filter by `product.template` ID (akan dicari semua variannya)
- `date_from` (optional): `YYYY-MM-DD` atau `YYYY-MM-DD HH:MM:SS`
- `date_to` (optional): `YYYY-MM-DD` atau `YYYY-MM-DD HH:MM:SS`
- `period` (optional): `today`, `yesterday`, `this_week`, `last_7_days`, `this_month`, `last_month`, `this_year`
- `limit` (optional): jumlah grup produk (default `100`)
- `offset` (optional): offset grup produk (default `0`)

Note:
- Jika `period` dikirim, sistem akan otomatis mengisi rentang tanggal.
- Jika `date_from` / `date_to` juga dikirim, nilai manual diprioritaskan.

**Response**:

```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "product_id": 112,
      "product_name": "JF Plus",
      "oee_records_count": 8,
      "avg_kpi": {
        "qty_planned": 2000.0,
        "qty_finished": 1987.5,
        "variance_finished": -12.5,
        "yield_percent": 99.375,
        "qty_bom_consumption": 1875.0,
        "qty_actual_consumption": 1894.2,
        "variance_consumption": 19.2,
        "consumption_ratio": 101.024
      },
      "last_oee_date": "2026-02-16 09:40:00"
    }
  ],
  "summary": {
    "total_products": 2,
    "total_oee_records": 13,
    "date_from": "2026-02-01 00:00:00",
    "date_to": "2026-02-29 23:59:59"
  },
  "chart_kpi_by_product": {
    "x_axis": ["JF Plus", "Product B"],
    "y_axis": {
      "qty_planned": [2000.0, 1500.0],
      "qty_finished": [1987.5, 1488.0],
      "yield_percent": [99.375, 99.2],
      "consumption_ratio": [101.024, 100.3]
    }
  },
  "chart_kpi_trend": {
    "x_axis": ["2026-02-01", "2026-02-02", "2026-02-03"],
    "y_axis": {
      "yield_percent": [98.9, 99.1, 99.4],
      "consumption_ratio": [100.8, 101.0, 100.6]
    }
  }
}
```

**cURL Example (JSON-RPC)**:
```bash
curl -X POST http://localhost:8069/api/scada/kpi-product-report \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "period": "this_month",
      "limit": 100,
      "offset": 0
    }
  }'
```

---

### 20B. Today Reports Dashboard (Protected)

**Get 4 laporan harian SCADA dalam 1 endpoint**

```http
POST /api/scada/today-reports
Auth: Session cookie
Content-Type: application/json
```

**JSON-RPC Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "date": "2026-02-17",
    "limit": 200
  }
}
```

**Parameters**:
- `date` (optional): tanggal report `YYYY-MM-DD` (default: hari ini server)
- `limit` (optional): jumlah data titik grafik deviasi batch (default `200`)

**Response**:

```json
{
  "status": "success",
  "report_date": "2026-02-17",
  "date_from": "2026-02-17 00:00:00",
  "date_to": "2026-02-17 23:59:59",
  "batch_status": {
    "scheduled_total": 12,
    "completed": 7,
    "unfinished": 5
  },
  "total_production_today": {
    "qty_finished": 13840.5,
    "completed_batch_count": 7
  },
  "oee_quality_today": {
    "oee_records_count": 7,
    "avg_yield_percent": 98.34,
    "avg_consumption_ratio": 101.12,
    "avg_oee_silo_percent": 96.8,
    "avg_max_abs_deviation_percent": 3.7,
    "total_deviation_alerts": 4,
    "by_equipment": [
      {
        "equipment_id": 1,
        "equipment_name": "Main PLC - Injection Machine 01",
        "oee_records_count": 4,
        "avg_yield_percent": 99.1,
        "avg_consumption_ratio": 100.4,
        "avg_oee_silo_percent": 97.5,
        "avg_max_abs_deviation_percent": 2.9,
        "total_deviation_alerts": 2
      }
    ]
  },
  "batch_to_batch_deviation_chart": {
    "count": 7,
    "data": [
      {
        "oee_id": 321,
        "mo_id": "MO/2026/0021",
        "equipment_id": 1,
        "equipment_name": "Main PLC - Injection Machine 01",
        "date_done": "2026-02-17T08:25:00",
        "variance_finished": -12.5,
        "variance_consumption": 18.0,
        "max_abs_deviation_percent": 4.2,
        "avg_silo_oee_percent": 95.8
      }
    ]
  }
}
```

Keterangan 4 laporan:
1. `batch_status`: batch selesai vs belum selesai (berdasarkan batch terjadwal start di tanggal report)
2. `total_production_today`: total `qty_finished` dari OEE pada tanggal report
3. `oee_quality_today`: kualitas OEE rata-rata harian total + per SCADA equipment
4. `batch_to_batch_deviation_chart`: data deret batch untuk grafik deviasi antar batch

**cURL Example (JSON-RPC)**:
```bash
curl -X POST http://localhost:8069/api/scada/today-reports \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "date": "2026-02-17",
      "limit": 200
    }
  }'
```

---

### 20C. Periodic Report Dashboard (Protected)

**Get laporan periodik sesuai pilihan waktu (7 report dalam 1 endpoint)**

```http
POST /api/scada/periodic-report
Auth: Session cookie
Content-Type: application/json
```

**JSON-RPC Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "period": "this_month",
    "date_from": "2026-02-01",
    "date_to": "2026-02-29",
    "product_id": 112,
    "product_tmpl_id": null,
    "raw_material_id": null,
    "raw_material_tmpl_id": null,
    "equipment_id": null,
    "equipment_code": null,
    "limit": 1000
  }
}
```

**Parameters**:
- `period` (optional): `today`, `yesterday`, `this_week`, `last_7_days`, `this_month`, `last_month`, `this_year`
- `date_from` / `date_to` (optional): override rentang periode (`YYYY-MM-DD` atau datetime)
- `product_id` / `product_tmpl_id` (optional): filter finished goods
- `raw_material_id` / `raw_material_tmpl_id` (optional): filter raw material
- `equipment_id` / `equipment_code` (optional): filter equipment
- `limit` (optional): batas data chart/table berbasis record (default `1000`)

**Response blocks**:
1. `metrics_total_production`
2. `metrics_total_mo`
3. `metrics_avg_oee_quality`
4. `chart_daily_target_vs_actual` (2 bar: target vs actual)
5. `chart_raw_material_consumption`
6. `table_silo_consumption_stock` (consumption + stock awal/akhir)
7. `table_daily_finished_goods`

**cURL Example (JSON-RPC)**:
```bash
curl -X POST http://localhost:8069/api/scada/periodic-report \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "period": "this_month",
      "raw_material_id": 45,
      "product_id": 112
    }
  }'
```

---

### 21. Get Product List (Protected)

**Retrieve Product List**

```http
GET /api/scada/products?category_id=1&category_name=Raw&active=true&limit=100&offset=0
Auth: Session cookie
```

**JSON-RPC (POST)**:

```http
POST /api/scada/products
Auth: Session cookie
Content-Type: application/json
```

**JSON-RPC Body**:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "category_id": 1,
    "category_name": "Raw",
    "active": "true",
    "limit": 100,
    "offset": 0
  }
}
```

**Query Parameters**:
- `category_id` (optional): Product category ID
- `category_name` (optional): Product category name (ilike)
- `active` (optional): true | false | all (default: true)
- `limit` (optional): Max records (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response**:

```json
[
  {
    "product_id": 1,
    "product_name": "Raw Material A",
    "product_tmpl_id": 1,
    "product_category": "Raw",
    "product_type": "product"
  },
  {
    "product_id": 2,
    "product_name": "Raw Material B",
    "product_tmpl_id": 2,
    "product_category": "Raw",
    "product_type": "product"
  }
]
```

Note: `product_tmpl_id` is included to support BoM lookup (template-level BoM).

**cURL Example**:
```bash
curl -X GET "http://localhost:8069/api/scada/products?category_name=Raw&active=true" \
  -b cookies.txt
```

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/products \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "limit": 100
    }
  }'
```

---

### 22. Get Product List by Category (Protected)

**Retrieve Product List with Category Filter (JSON-RPC)**

```http
POST /api/scada/products-by-category
Auth: Session cookie
Content-Type: application/json
```

**Query Parameters**:
- `category_id` (optional): Product category ID
- `category_name` (optional): Product category name (ilike)
- `active` (optional): true | false | all (default: true)
- `limit` (optional): Max records (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response**: Same as [Get Product List](#14-get-product-list-protected).

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/products-by-category \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "category_name": "Raw",
      "limit": 100
    }
  }'
```

**Example Response**:
```json
[
  {
    "product_id": 1,
    "product_name": "Raw Material A",
    "product_tmpl_id": 1,
    "product_category": "Raw",
    "product_type": "product"
  }
]
```

---

### 23. Get BoM List (Protected)

**Retrieve BoM list with components**

```http
GET /api/scada/boms?product_tmpl_id=123&limit=50&offset=0
Auth: Session cookie
```

**JSON-RPC (POST)**:

```http
POST /api/scada/boms
Auth: Session cookie
Content-Type: application/json
```

**Query Parameters**:
- `bom_id` (optional): BoM ID
- `product_tmpl_id` (optional): Product template ID (recommended for template-level BoM)
- `product_id` (optional): Product variant ID (will be mapped to template if possible)
- `active` (optional): true | false | all (default: true)
- `limit` (optional): Max records (default: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response**:

```json
[
  {
    "bom_id": 10,
    "bom_code": "BOM-0001",
    "product_tmpl_id": 5,
    "product_tmpl_name": "Feed Mix A",
    "product_id": 12,
    "product_name": "Feed Mix A (25kg)",
    "product_qty": 1.0,
    "uom": "Units",
    "type": "normal",
    "components": [
      {
        "product_id": 101,
        "product_name": "Jagung Giling",
        "quantity": 20.0,
        "uom": "kg"
      },
      {
        "product_id": 102,
        "product_name": "Bungkil Kedelai",
        "quantity": 5.0,
        "uom": "kg"
      }
    ]
  }
]
```

Note: `product_id` is only included when the BoM is specific to a product variant. For template-level BoM, use `product_tmpl_id`.

**cURL Example**:
```bash
curl -X GET "http://localhost:8069/api/scada/boms?product_id=123&limit=50" \
  -b cookies.txt
```

**JSON-RPC Example**:
```bash
curl -X POST http://localhost:8069/api/scada/boms \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "jsonrpc": "2.0",
    "method": "call",
    "params": {
      "product_tmpl_id": 123,
      "limit": 50
    }
  }'
```

---

### 24. Create Failure Report (Extension Module, Protected)

**Create SCADA equipment failure report**

Available only when module `grt_scada_failure_report` is installed.

```http
POST /api/scada/failure-report
Auth: Session cookie
Content-Type: application/json
```

**Request Body**:

```json
{
  "equipment_code": "PLC01",
  "description": "Motor overload saat proses mixing",
  "date": "2026-02-15 08:30:00"
}
```

**Field notes**:
- `equipment_code` (required): nilai `equipment_code` pada model `scada.equipment`
- `description` (required): deskripsi failure
- `date` (optional): format `YYYY-MM-DD HH:MM:SS` atau `YYYY-MM-DDTHH:MM`; jika kosong akan pakai waktu server saat create

**Response (Success)**:

```json
{
  "status": "success",
  "message": "Failure report created",
  "data": {
    "id": 1,
    "equipment_code": "PLC01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15 08:30:00"
  }
}
```

**Response (Error)**:

```json
{
  "status": "error",
  "message": "Equipment with code \"PLC01\" not found"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8069/api/scada/failure-report \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_code": "PLC01",
    "description": "Motor overload saat proses mixing",
    "date": "2026-02-15 08:30:00"
  }'
```

**Form Routes**:
- `GET /scada/failure-report/input`
- `POST /scada/failure-report/submit`

---

## Error Handling

### Common Error Codes & Messages

| HTTP Status | Message | Meaning |
|---|---|---|
| 400 | Equipment not found | Equipment code tidak valid |
| 400 | Product not found | Product ID tidak ada di sistem |
| 400 | Validation failed | Data tidak valid |
| 401 | Unauthorized | Session tidak valid atau expired |
| 404 | MO record not found | Record ID tidak valid |
| 500 | Server error | Error di backend |

### Example Error Response

```json
{
  "status": "error",
  "message": "Equipment not found: PLC99"
}
```

---

## Integration Examples

### JavaScript/Vue.js

```javascript
// Using fetch (session stored in cookies)
async function login() {
  const response = await fetch('http://localhost:8069/api/scada/authenticate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      db: 'your_database',
      login: 'admin',
      password: 'admin'
    }),
    credentials: 'include'
  });

  const result = await response.json();
  if (result.status === 'error') {
    throw new Error(result.message);
  }
}

async function createMaterialConsumption(data) {
  const response = await fetch(
    'http://localhost:8069/api/scada/material-consumption',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
      credentials: 'include'
    }
  );
  
  const result = await response.json();
  if (result.status === 'error') {
    throw new Error(result.message);
  }
  return result;
}

// Usage
try {
  await login();
  const result = await createMaterialConsumption({
    equipment_id: 'PLC01',
    product_tmpl_id: 123,
    quantity: 10.5,
    timestamp: new Date().toISOString(),
    mo_id: 'MO/2025/001'
  });
  console.log('Record created:', result.record_id);
} catch (error) {
  console.error('Error:', error.message);
}
```

### Python

```python
import requests
from datetime import datetime

base_url = 'http://localhost:8069/api/scada'
session = requests.Session()

# Authenticate and store session cookie
auth_response = session.post(
  f'{base_url}/authenticate',
  json={
    'db': 'your_database',
    'login': 'admin',
    'password': 'admin'
  }
)
auth_result = auth_response.json()
if auth_result.get('status') == 'error':
  raise RuntimeError(auth_result.get('message'))

# Create material consumption
data = {
    'equipment_id': 'PLC01',
  'product_tmpl_id': 123,
    'quantity': 10.5,
    'timestamp': datetime.now().isoformat(),
    'mo_id': 'MO/2025/001'
}

response = session.post(f'{base_url}/material-consumption', json=data)

result = response.json()
if result['status'] == 'success':
    print(f"Created record: {result['record_id']}")
else:
    print(f"Error: {result['message']}")
```

### cURL

```bash
#!/bin/bash

BASE_URL="http://localhost:8069/api/scada"

# Authenticate and store session cookie
curl -X POST "${BASE_URL}/authenticate" \
  -H "Content-Type: application/json" \
  -d '{"db": "your_database", "login": "admin", "password": "admin"}' \
  -c cookies.txt

# Health check
curl -X GET "${BASE_URL}/health"

# Create material consumption
curl -X POST "${BASE_URL}/material-consumption" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "product_tmpl_id": 123,
    "quantity": 10.5,
    "timestamp": "2025-02-06T10:30:00",
    "mo_id": "MO/2025/001"
  }'

# Get MO list
curl -X GET "${BASE_URL}/mo-list?equipment_id=PLC01" \
  -b cookies.txt

# Mark MO done
curl -X POST "${BASE_URL}/mo/mark-done" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "equipment_id": "PLC01",
    "mo_id": "MO/2025/001",
    "finished_qty": 1000.0,
    "auto_consume": true,
    "date_end_actual": "2025-02-06T16:00:00"
  }'
```

---

## Best Practices

1. **Always use HTTPS in production**
2. **Keep session cookies secure** - avoid exposing cookies in logs
3. **Handle errors gracefully** - check `status` field before accessing `data`
4. **Add request timeouts** - prevent hanging requests
5. **Validate data** - use the `/validate` endpoints before creating records
6. **Log API calls** - important untuk troubleshooting
7. **Rate limiting** - implement backoff for failed requests
8. **Async operations** - don't block UI on API calls

---

## Documentation

- **Vue.js Integration**: See [JSONRPC_VUEJS_GUIDE.md](JSONRPC_VUEJS_GUIDE.md)
- **Python Integration**: See [JSONRPC_VUEJS_GUIDE.md](JSONRPC_VUEJS_GUIDE.md) (Python examples section)
- **Troubleshooting**: See main [README.md](README.md)
