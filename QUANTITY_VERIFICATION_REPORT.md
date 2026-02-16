# ✅ Quantity (actual_weight_finished_good) Verification

## Status: VERIFIED ✅

Quantity yang merupakan `actual_weight_quantity_finished_goods` dari PLC sudah dikonfigurasi untuk dikirimkan ke Odoo endpoint `/api/scada/mo/update-with-consumptions` untuk update `stock.move.line`.

---

## Flow Lengkap

### 1. Task 3 (Scheduler) - Extract Quantity
**Lokasi**: `app/core/scheduler.py` lines 337-345

```python
batch_data = {
    "status_manufacturing": 1,
    "actual_weight_quantity_finished_goods": (  # ← QUANTITY dari PLC
        float(batch.actual_weight_quantity_finished_goods)
        if batch.actual_weight_quantity_finished_goods is not None
        else 0.0
    ),
}
```

### 2. OdooConsumptionService - Extract & Pass Quantity
**Lokasi**: `app/services/odoo_consumption_service.py` lines ~765-778

```python
if consumption_entries:
    # Extract quantity (actual_weight_finished_good) untuk update stock.move.line
    quantity = batch_data.get("actual_weight_quantity_finished_goods")
    if quantity is not None:
        try:
            quantity = float(quantity)
        except (TypeError, ValueError):
            quantity = None
    
    update_result[
        "consumption_details"
    ] = await self.update_consumption_with_odoo_codes(
        mo_id=mo_id,
        consumption_data=consumption_entries,
        quantity=quantity,  # ← PASS QUANTITY HERE
    )
```

### 3. Update Consumption with Odoo Codes - Add to Payload
**Lokasi**: `app/services/odoo_consumption_service.py` lines 248-253

```python
# Build payload untuk Odoo endpoint
payload: Dict[str, Any] = {
    "mo_id": mo_id,
}

if quantity and quantity > 0:
    payload["quantity"] = float(quantity)  # ← ADD QUANTITY TO PAYLOAD

# Add all consumption data
payload.update(converted_data)

logger.debug(f"Complete payload to /update-with-consumptions: {payload}")
```

### 4. Send to Odoo Endpoint
**Lokasi**: `app/services/odoo_consumption_service.py` line 265

```python
response = await client.post(update_endpoint, json=payload)
```

---

## Payload Example

**Sebelum fix** ❌
```json
{
  "mo_id": "WH/MO/00001",
  "silo101": 825,
  "silo102": 600,
  "silo103": 375.15
}
```
(Quantity tidak ada → stock.move.line tidak terupdate)

**Sesudah fix** ✅
```json
{
  "mo_id": "WH/MO/00001",
  "quantity": 2500.75,
  "silo101": 825,
  "silo102": 600,
  "silo103": 375.15
}
```
(Quantity ada → stock.move.line akan terupdate dengan 2500.75)

---

## Verification

Untuk memverifikasi bahwa quantity dikirimkan dengan benar:

1. **Lihat logs saat Task 3 berjalan:**
   ```
   [TASK 3-DEBUG-7] Weight: 2500.75
   Complete payload to /update-with-consumptions: {'mo_id': 'WH/MO/00001', 'quantity': 2500.75, 'silo101': 825, ...}
   ```

2. **Run test script:**
   ```bash
   python test_quantity_payload.py
   ```
   Output akan menunjukkan `quantity` di payload

3. **Check di Odoo:**
   - Buka MO di Odoo
   - Lihat `stock.move.line` untuk setiap component
   - Field `quantity` harus = `actual_weight_finished_good` dari PLC

---

## Checklist

- ✅ `actual_weight_quantity_finished_goods` di-extract dari `batch_data` di Task 3
- ✅ `quantity` di-extract dan di-pass ke `update_consumption_with_odoo_codes()`
- ✅ `quantity` ditambahkan ke payload sebelum dikirim ke Odoo
- ✅ Debug logging ditambahkan untuk verifikasi payload
- ✅ Parameter `quantity` sudah ada di method signature `update_consumption_with_odoo_codes()`

**READY FOR TESTING ✅**
