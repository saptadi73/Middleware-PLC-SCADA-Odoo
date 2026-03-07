# Kontrak Endpoint Final - Update MO with Consumptions

Dokumen ini adalah kontrak implementasi singkat untuk sinkronisasi Middleware → Odoo pada endpoint update consumption.

## Endpoint Utama

- Method: `POST`
- URL: `/api/scada/mo/update-with-consumptions`
- Auth: session cookie (didapat dari endpoint auth)

## Endpoint Auth (dipakai middleware)

1. Primary:
- Method: `POST`
- URL: `/api/scada/authenticate`
- Body:
```json
{
  "db": "your_database",
  "login": "your_user",
  "password": "your_password"
}
```

2. Fallback:
- Method: `POST`
- URL: `/web/session/authenticate`
- Body JSON-RPC standar Odoo.

## Kontrak Request - update-with-consumptions

### Field wajib
- `mo_id` (string): contoh `WH/MO/00051`

### Field opsional
- `quantity` (number): **actual weight finished goods** dari middleware
  - Bukan target planning/rescale
  - Middleware hanya kirim jika `quantity > 0`
- `silo101 ... silo115` (number): actual consumption per equipment code
  - Hanya nilai `> 0` yang dikirim

### Format key konsumsi yang direkomendasikan
- Gunakan equipment code numerik lowercase: `silo101..silo115`
- Middleware juga bisa mengonversi dari `scada_tag` (`silo_a`, `lq_tetes`, dll), tetapi untuk kontrak antarsistem disarankan tetap `silo10x/silo11x`.

### Contoh payload minimal
```json
{
  "mo_id": "WH/MO/00051",
  "silo101": 205.12,
  "silo102": 212.8
}
```

### Contoh payload lengkap (sesuai flow middleware)
```json
{
  "mo_id": "WH/MO/00051",
  "quantity": 1000.0,
  "silo101": 205.12,
  "silo102": 212.8,
  "silo103": 129.3,
  "silo104": 193.3,
  "silo105": 203.54,
  "silo106": 182.54,
  "silo107": 213.78,
  "silo108": 192.75,
  "silo109": 287.81,
  "silo110": 285.46,
  "silo111": 218.9,
  "silo112": 174.76,
  "silo113": 183.06,
  "silo114": 198.42,
  "silo115": 169.28
}
```

## Kontrak Response

### Success penuh
```json
{
  "status": "success",
  "message": "MO updated successfully",
  "mo_id": "WH/MO/00051",
  "mo_state": "confirmed",
  "updated_finished_qty": 1000.0,
  "consumed_items": [
    {
      "equipment_code": "silo101",
      "applied_qty": 205.12,
      "move_ids": [123],
      "products": ["Pollard Angsa"]
    }
  ],
  "errors": []
}
```

### Success parsial
```json
{
  "status": "success",
  "message": "MO updated with some errors",
  "mo_id": "WH/MO/00051",
  "mo_state": "confirmed",
  "updated_finished_qty": 1000.0,
  "consumed_items": [
    {
      "equipment_code": "silo101",
      "applied_qty": 205.12,
      "move_ids": [123],
      "products": ["Pollard Angsa"]
    }
  ],
  "errors": [
    "silo999: Equipment not found"
  ]
}
```

### Error
```json
{
  "status": "error",
  "message": "Manufacturing Order \"WH/MO/99999\" not found"
}
```

## Aturan Bisnis yang Perlu Disepakati

1. `quantity` diperlakukan sebagai actual finished goods (update `quantity_done` finished move), bukan mark-done.
2. Endpoint boleh memproses partial success: item valid tetap jalan, item invalid masuk `errors`.
3. Endpoint harus idempotent per nilai terbaru yang dikirim middleware.
4. MO `done/cancel` harus ditolak dengan response error yang jelas.
5. Tidak ada requirement rescale target MO pada endpoint ini; jika dibutuhkan, gunakan field target eksplisit yang terpisah dari `quantity`.

## Catatan Operasional Middleware

- Middleware melakukan warning `ATTENTION_SUSPICIOUS_VALUE` jika `quantity` melewati batas kapasitas batch konfigurasi.
- Warning tidak memblokir request (warning-only mode), agar operator tetap bisa lakukan tindakan manual/cancel di Odoo.
