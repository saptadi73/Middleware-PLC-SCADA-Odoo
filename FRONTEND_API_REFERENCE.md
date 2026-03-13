# Frontend API Reference

Dokumen ini adalah rujukan tunggal untuk frontend terhadap seluruh endpoint middleware FastAPI yang ada di repo ini.

Dokumen ini hanya mencakup middleware ini saja dan tidak memasukkan `API_SPEC.md`, karena dokumen tersebut menjelaskan kontrak API Odoo yang berbeda fungsi.

## Arsitektur Singkat

Frontend mengakses middleware FastAPI ini.

Base URL lokal umum:

`http://localhost:8000`

## Konvensi Integrasi

### 1. Middleware FastAPI

- Format response umumnya:

```json
{
  "status": "success",
  "message": "optional message",
  "data": {}
}
```

- Endpoint middleware dipakai untuk:
  - monitoring scheduler
  - kontrol batch/TASK1/TASK2/TASK3
  - PLC read/write
  - log viewer

## Wrapper Frontend Yang Disarankan

### Wrapper FastAPI

```javascript
export async function callMiddleware(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  const data = await response.json();

  if (!response.ok || data?.status === 'error') {
    throw new Error(data?.detail || data?.message || 'Middleware request failed');
  }

  return data;
}
```

## Bagian A. FastAPI Middleware Endpoints

Semua endpoint di bawah ini berasal dari route yang benar-benar terdaftar di aplikasi FastAPI repo ini.

### A1. Health and Auth

| Method | Path | Tujuan | Catatan Frontend |
| --- | --- | --- | --- |
| GET | `/api/health` | Health check aplikasi middleware | Bisa dipakai untuk status backend live |
| POST | `/api/scada/authenticate` | Authenticate ke Odoo via middleware | Dipakai bila frontend ingin minta middleware membuat session Odoo |

### A2. Scheduler and Admin Control

| Method | Path | Tujuan | Catatan Frontend |
| --- | --- | --- | --- |
| POST | `/api/admin/reset-task1-start` | Reset awal TASK1: set WRITE `status_read_data=1` lalu clear `mo_batch` | Endpoint utama untuk tombol `Mulai dari Awal` |
| POST | `/api/admin/clear-mo-batch` | Hapus semua isi `mo_batch` | Tidak mengubah handshake PLC |
| POST | `/api/admin/trigger-sync` | Trigger TASK1 manual | Cocok dipanggil setelah reset-task1-start |
| GET | `/api/admin/batch-status` | Status queue batch aktif | Endpoint monitoring utama frontend operasi |
| GET | `/api/admin/table/mo-batch` | Data tabel `mo_batch` siap tampil | Untuk halaman queue batch aktif |
| GET | `/api/admin/table/mo-histories` | Data tabel `mo_histories` dengan pagination | Untuk halaman riwayat besar (banyak data) |
| GET | `/api/admin/monitor/real-time` | Dashboard status batch real-time | Cocok untuk screen monitoring |
| GET | `/api/admin/task-monitor/summary` | Ringkasan status TASK1-TASK4 dari log scheduler | Cocok untuk kartu status per TASK |
| GET | `/api/admin/task-monitor/errors` | Alert agregat ERROR/CRITICAL (opsional WARNING) per TASK | Cocok untuk panel alert/error center |
| GET | `/api/admin/task-monitor/errors/flat` | Alert gabungan semua TASK dalam satu list terurut waktu | Cocok untuk notification feed global |
| GET | `/api/admin/task-monitor/{task_name}` | Detail log satu TASK (`task1`, `task2`, `task3`, `task4`) | Cocok untuk panel terminal/log viewer per TASK |
| GET | `/api/admin/history` | Riwayat batch | Support query `limit` dan `offset` |
| GET | `/api/admin/history/{mo_id}` | Detail riwayat per MO | Cocok untuk detail modal/history view |
| POST | `/api/admin/manual/retry-push-odoo/{mo_id}` | Retry push completed batch ke Odoo | Untuk batch yang pending sync |
| POST | `/api/admin/manual/reset-batch/{mo_id}` | Reset status batch jadi belum selesai | Query opsional `push_to_plc=true` |
| POST | `/api/admin/manual/cancel-batch/{batch_no}` | Cancel batch dan pindahkan ke history | Query/body sederhana; `notes` opsional |
| POST | `/api/admin/manual/trigger-plc-sync` | Trigger TASK2 manual | Untuk debug/ops manual |
| POST | `/api/admin/manual/trigger-process-completed` | Trigger TASK3 manual | Untuk force archive/sync completed |
| GET | `/api/admin/failed-to-push` | Daftar batch completed yang gagal push ke Odoo | Cocok untuk halaman exception queue |

### A3. PLC Endpoints

| Method | Path | Tujuan | Catatan Frontend |
| --- | --- | --- | --- |
| POST | `/api/plc/write-field` | Tulis satu field PLC | Perlu body `batch_name`, `field_name`, `value` |
| POST | `/api/plc/write-batch` | Tulis banyak field ke satu batch PLC | Perlu body `batch_name`, `data` |
| POST | `/api/plc/write-mo-batch` | Ambil batch dari DB lalu tulis ke PLC | Perlu body `batch_no`, `plc_batch_slot` |
| GET | `/api/plc/config` | Ambil config PLC aktif | Cocok untuk halaman diagnostics |
| GET | `/api/plc/read-field/{field_name}` | Baca satu field dari PLC | Query `batch_no=1..10` |
| GET | `/api/plc/read-all` | Baca semua field batch read PLC | Query `batch_no=1..10` |
| GET | `/api/plc/read-batch` | Baca batch PLC terformat | Query `batch_no=1..10` |
| GET | `/api/plc/read-batch-all` | Baca semua batch read area PLC | Cocok untuk halaman debug PLC |
| POST | `/api/plc/sync-from-plc` | Sinkronkan data PLC ke `mo_batch` | Trigger manual TASK2 versi endpoint |

### A4. Consumption and MO Endpoints via Middleware

| Method | Path | Tujuan | Catatan Frontend |
| --- | --- | --- | --- |
| POST | `/api/scada/mo-list-detailed` | Fetch detailed MO dari Odoo dan sync ke DB lokal | Query `limit`, `offset` |
| POST | `/api/consumption/update` | Update consumption manual per komponen | Perlu body `mo_id`, `equipment_id`, `consumption_data` |
| POST | `/api/consumption/mark-done` | Mark MO done | Perlu body `mo_id`, `finished_qty`, optional `equipment_id`, `auto_consume` |
| POST | `/api/consumption/batch-process` | Proses batch consumption otomatis | Endpoint batch update paling efisien di middleware |
| POST | `/api/api/scada/equipment-failure` | Buat equipment failure report via middleware | Path ini memang terdaftar seperti itu di code saat ini |

### A5. Logs

Prefix router logs adalah `/api/logs`.

| Method | Path | Tujuan | Catatan Frontend |
| --- | --- | --- | --- |
| GET | `/api/logs/` | Ambil system logs | Support `skip`, `limit`, `level`, `module`, `search`, `start_time`, `end_time` |
| DELETE | `/api/logs/clear` | Bersihkan logs | Support `keep_last` dan `older_than_days` |

### A6. Equipment Failure Form Routes

Endpoint ini berada di luar prefix `/api`.

| Method | Path | Tujuan | Catatan Frontend |
| --- | --- | --- | --- |
| GET | `/scada/failure-report/input` | Menampilkan form HTML bawaan | Lebih cocok untuk testing/manual input |
| POST | `/scada/failure-report/submit` | Submit form failure report | Form-data: `equipment_code`, `description`, optional `date` |

## Bagian B. FastAPI Request Body Ringkas

### B1. POST `/api/admin/reset-task1-start`

Body: tidak perlu body

Response penting:

```json
{
  "status": "success",
  "message": "TASK 1 initial state prepared successfully",
  "data": {
    "write_ready_addresses": ["D7076", "D7176"],
    "write_ready_count": 10,
    "deleted_mo_batch_count": 7
  }
}
```

### B2. POST `/api/consumption/update`

```json
{
  "mo_id": "MO/2025/001",
  "equipment_id": "PLC01",
  "consumption_data": {
    "silo_a": 50.5,
    "silo_b": 25.3
  },
  "timestamp": "2025-02-13T10:30:00"
}
```

### B3. POST `/api/consumption/mark-done`

```json
{
  "mo_id": "MO/2025/001",
  "finished_qty": 1000,
  "equipment_id": "PLC01",
  "auto_consume": true,
  "message": "optional note"
}
```

### B4. POST `/api/consumption/batch-process`

```json
{
  "mo_id": "MO/2025/001",
  "equipment_id": "PLC01",
  "batch_data": {
    "consumption_silo_a": 50.5,
    "consumption_silo_b": 25.3,
    "status_manufacturing": 1,
    "actual_weight_quantity_finished_goods": 1000
  }
}
```

### B5. POST `/api/plc/write-field`

```json
{
  "batch_name": "BATCH01",
  "field_name": "NO-MO",
  "value": "WH/MO/00002"
}
```

### B6. POST `/api/plc/write-batch`

```json
{
  "batch_name": "BATCH01",
  "data": {
    "BATCH": 1,
    "NO-MO": "WH/MO/00002"
  }
}
```

### B7. POST `/api/plc/write-mo-batch`

```json
{
  "batch_no": 1,
  "plc_batch_slot": 1
}
```

### B8. GET `/api/admin/task-monitor/summary`

Query opsional:

- `since_minutes=180` untuk mengambil ringkasan 3 jam terakhir

Response penting:

```json
{
  "status": "success",
  "data": {
    "since_minutes": 180,
    "tasks": [
      {
        "task": "task1",
        "label": "TASK 1",
        "description": "Auto-sync MO dari Odoo ke mo_batch dan PLC WRITE area",
        "status": "success",
        "latest_level": "INFO",
        "last_run_at": "2026-03-13T08:21:10.123456+00:00",
        "latest_message": "[TASK 1] Auto-sync committed successfully: staged=4, written=4",
        "log_counts": {
          "total": 12,
          "info": 10,
          "warning": 1,
          "error": 1
        }
      }
    ]
  }
}
```

### B9. GET `/api/admin/task-monitor/{task_name}`

Path param:

- `task_name`: `task1`, `task2`, `task3`, atau `task4`

Query opsional:

- `limit=50`
- `skip=0`
- `since_minutes=180`
- `level=INFO|WARNING|ERROR`

Response penting:

```json
{
  "status": "success",
  "data": {
    "summary": {
      "task": "task2",
      "label": "TASK 2",
      "status": "running",
      "latest_level": "INFO",
      "last_run_at": "2026-03-13T08:25:10.123456+00:00",
      "latest_message": "[TASK 2] Updated 3 batch(es) from PLC (processed=3, failed=0)",
      "log_counts": {
        "total": 25,
        "info": 22,
        "warning": 2,
        "error": 1
      }
    },
    "filters": {
      "task": "task2",
      "label": "TASK 2",
      "prefix": "[TASK 2]",
      "since_minutes": 180,
      "level": null,
      "skip": 0,
      "limit": 50
    },
    "logs": [
      {
        "timestamp": "2026-03-13T08:25:10.123456+00:00",
        "level": "INFO",
        "module": "app.core.scheduler",
        "message": "[TASK 2] Updated 3 batch(es) from PLC (processed=3, failed=0)",
        "batch_no": null,
        "mo_id": null
      }
    ],
    "meta": {
      "total": 25,
      "has_next": false
    }
  }
}
```

### B10. GET `/api/admin/task-monitor/errors`

Query opsional:

- `since_minutes=180`
- `limit_per_task=5`
- `include_warning=true`

Response penting:

```json
{
  "status": "success",
  "data": {
    "since_minutes": 180,
    "levels": ["ERROR", "CRITICAL", "WARNING"],
    "limit_per_task": 5,
    "total_alerts": 3,
    "tasks": {
      "task1": [
        {
          "timestamp": "2026-03-13T08:30:00+00:00",
          "level": "ERROR",
          "module": "app.core.scheduler",
          "message": "[TASK 1] ERROR in auto-sync task: PLC write timeout"
        }
      ],
      "task2": [],
      "task3": [],
      "task4": []
    }
  }
}
```

### B11. GET `/api/admin/task-monitor/errors/flat`

Query opsional:

- `since_minutes=180`
- `skip=0`
- `limit=100`
- `include_warning=true`

Response penting:

```json
{
  "status": "success",
  "data": {
    "since_minutes": 180,
    "levels": ["ERROR", "CRITICAL", "WARNING"],
    "total_alerts": 4,
    "skip": 0,
    "limit": 100,
    "has_next": false,
    "items": [
      {
        "timestamp": "2026-03-13T08:30:00+00:00",
        "level": "ERROR",
        "module": "app.core.scheduler",
        "message": "[TASK 1] ERROR in auto-sync task: PLC write timeout",
        "task": "task1",
        "task_label": "TASK 1",
        "task_prefix": "[TASK 1]"
      }
    ]
  }
}
```

### B12. GET `/api/admin/table/mo-batch`

Body: tidak perlu body

Response penting:

```json
{
  "status": "success",
  "data": {
    "total": 3,
    "items": [
      {
        "batch_no": 1,
        "mo_id": "WH/MO/00001",
        "equipment_id_batch": "PLC01",
        "status_manufacturing": false,
        "status_operation": false,
        "last_read_from_plc": "2026-03-13T09:00:00+00:00"
      }
    ]
  }
}
```

### B13. GET `/api/admin/table/mo-histories`

Query opsional:

- `limit=100`
- `offset=0`
- `status=completed|failed|cancelled`
- `mo_id=WH/MO/00001` (supports partial search)

Response penting:

```json
{
  "status": "success",
  "data": {
    "total": 1260,
    "limit": 100,
    "offset": 0,
    "has_next": true,
    "items": [
      {
        "batch_no": 8,
        "mo_id": "WH/MO/00888",
        "status": "completed",
        "notes": null,
        "last_read_from_plc": "2026-03-13T08:55:00+00:00"
      }
    ]
  }
}
```

Contoh query frontend (pagination + search):

`/api/admin/table/mo-histories?limit=50&offset=0&status=completed&mo_id=WH/MO/00`

## Bagian C. Endpoint Prioritas Untuk Frontend

Jika frontend hanya butuh endpoint yang paling sering dipakai, mulai dari daftar ini:

### C1. Halaman Operasional Middleware

| Kebutuhan UI | Endpoint |
| --- | --- |
| Status queue batch | `/api/admin/batch-status` |
| Monitoring real-time | `/api/admin/monitor/real-time` |
| Ringkasan TASK scheduler | `/api/admin/task-monitor/summary` |
| Alert ERROR/WARNING TASK | `/api/admin/task-monitor/errors` |
| Alert feed gabungan TASK | `/api/admin/task-monitor/errors/flat` |
| Detail log per TASK | `/api/admin/task-monitor/task1` |
| Reset TASK1 dari awal | `/api/admin/reset-task1-start` |
| Trigger sync TASK1 | `/api/admin/trigger-sync` |
| Daftar batch gagal push Odoo | `/api/admin/failed-to-push` |
| History batch | `/api/admin/history` |
| System logs | `/api/logs/` |

### C2. Halaman PLC and Diagnostics

| Kebutuhan UI | Endpoint |
| --- | --- |
| Baca semua data PLC batch tertentu | `/api/plc/read-batch?batch_no=1` |
| Baca semua batch PLC | `/api/plc/read-batch-all` |
| Trigger sync PLC ke DB | `/api/plc/sync-from-plc` |
| Lihat config PLC | `/api/plc/config` |

## Bagian D. Flow Frontend Yang Disarankan

### D1. Tombol `Mulai dari Awal` untuk TASK1

1. Panggil `POST /api/admin/reset-task1-start`
2. Jika operator ingin langsung jalan, panggil `POST /api/admin/trigger-sync`
3. Refresh `GET /api/admin/batch-status`

Contoh:

```javascript
export async function startTask1FromBeginning() {
  const reset = await callMiddleware('/api/admin/reset-task1-start', {
    method: 'POST',
  });

  const sync = await callMiddleware('/api/admin/trigger-sync', {
    method: 'POST',
  });

  const status = await callMiddleware('/api/admin/batch-status');

  return { reset, sync, status };
}
```

### D2. Halaman Monitoring Log

1. Panggil `GET /api/logs/?limit=100`
2. Gunakan filter `level`, `module`, `search`, `start_time`, `end_time` bila perlu
3. Gunakan `DELETE /api/logs/clear` hanya untuk admin tools

### D3. Halaman Monitoring TASK Scheduler

1. Panggil `GET /api/admin/task-monitor/summary?since_minutes=180` untuk isi kartu status TASK1-TASK4
2. Saat operator membuka salah satu TASK, panggil `GET /api/admin/task-monitor/task1?limit=50&since_minutes=180`
3. Untuk tab error-only, tambahkan query `level=ERROR`
4. Untuk panel alert global, panggil `GET /api/admin/task-monitor/errors?since_minutes=180&limit_per_task=5`
5. Untuk notification feed single-list, panggil `GET /api/admin/task-monitor/errors/flat?since_minutes=180&skip=0&limit=100`

Contoh:

```javascript
export async function loadTaskMonitorDashboard() {
  const summary = await callMiddleware('/api/admin/task-monitor/summary?since_minutes=180');
  const alerts = await callMiddleware('/api/admin/task-monitor/errors?since_minutes=180&limit_per_task=5');
  const alertFeed = await callMiddleware('/api/admin/task-monitor/errors/flat?since_minutes=180&skip=0&limit=100');
  const task1 = await callMiddleware('/api/admin/task-monitor/task1?limit=30&since_minutes=180');

  return {
    summary: summary.data,
    alerts: alerts.data,
    alertFeed: alertFeed.data,
    task1: task1.data,
  };
}
```

Contoh komponen ringkas panel alert (React):

```jsx
function TaskAlertPanel({ alerts }) {
  const entries = Object.entries(alerts?.tasks || {});

  return (
    <div>
      {entries.map(([task, items]) => (
        <section key={task}>
          <h4>{task.toUpperCase()}</h4>
          {!items.length ? (
            <p>No alert</p>
          ) : (
            <ul>
              {items.map((item) => (
                <li key={item.id}>
                  [{item.level}] {item.message}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
```

## Bagian E. Catatan Penting

1. Endpoint `POST /api/api/scada/equipment-failure` di middleware memang saat ini memiliki path ganda `/api/api/...` sesuai implementasi route yang ada sekarang.
2. Endpoint health di middleware muncul di path `/api/health`.
3. Route `/scada/failure-report/input` adalah halaman HTML siap pakai, bukan JSON API murni.
4. Dokumen ini sengaja hanya membahas middleware FastAPI di repo ini.
5. Jika frontend perlu terhubung langsung ke API Odoo, gunakan dokumen terpisah yang memang khusus untuk itu, bukan dokumen ini.
