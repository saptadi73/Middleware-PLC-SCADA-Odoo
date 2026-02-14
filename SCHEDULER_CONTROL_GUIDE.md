# Scheduler Task Control Guide

Panduan lengkap untuk mengontrol setiap scheduler task secara independent melalui konfigurasi .env.

---

## 📋 Overview

Sistem scheduler memiliki **4 task utama** yang dapat dikontrol secara individual:

| Task | Fungsi | Default Interval | Control Flag |
|------|--------|------------------|--------------|
| **Task 1** | Auto-sync MO dari Odoo | 60 menit | `ENABLE_TASK_1_AUTO_SYNC` |
| **Task 2** | PLC read sync (near real-time) | 5 menit | `ENABLE_TASK_2_PLC_READ` |
| **Task 3** | Process completed batches | 3 menit | `ENABLE_TASK_3_PROCESS_COMPLETED` |
| **Task 4** | Health monitoring | 10 menit | `ENABLE_TASK_4_HEALTH_MONITOR` |

---

## ⚙️ Configuration dalam .env

### Scheduler Enable/Disable Flags

```env
# Master switch untuk semua scheduler (masih berlaku)
ENABLE_AUTO_SYNC=true

# Individual Task Control (default semua true)
ENABLE_TASK_1_AUTO_SYNC=true
ENABLE_TASK_2_PLC_READ=true
ENABLE_TASK_3_PROCESS_COMPLETED=true
ENABLE_TASK_4_HEALTH_MONITOR=true
```

### Custom Intervals (Optional)

```env
# Task 1: Auto-sync MO interval
SYNC_INTERVAL_MINUTES=60

# Task 2: PLC read sync interval
PLC_READ_INTERVAL_MINUTES=5

# Task 3: Process completed batches interval
PROCESS_COMPLETED_INTERVAL_MINUTES=3

# Task 4: Health monitor interval
HEALTH_MONITOR_INTERVAL_MINUTES=10

# Global limit
SYNC_BATCH_LIMIT=10
```

---

## 🎯 Use Cases

### 1. **Development Mode** - Aktifkan hanya Task 1 & 2

```env
ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=true
ENABLE_TASK_2_PLC_READ=true
ENABLE_TASK_3_PROCESS_COMPLETED=false
ENABLE_TASK_4_HEALTH_MONITOR=false
```

**Hasil:** Hanya sync data Odoo dan read PLC, tidak ada processing/monitoring.

---

### 2. **Production Mode** - Semua aktif dengan interval tertentu

```env
ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=true
ENABLE_TASK_2_PLC_READ=true
ENABLE_TASK_3_PROCESS_COMPLETED=true
ENABLE_TASK_4_HEALTH_MONITOR=true

# Custom intervals untuk production
SYNC_INTERVAL_MINUTES=30
PLC_READ_INTERVAL_MINUTES=2
PROCESS_COMPLETED_INTERVAL_MINUTES=1
HEALTH_MONITOR_INTERVAL_MINUTES=5
```

**Hasil:** Full system runtime dengan monitoring lebih ketat.

---

### 3. **PLC Troubleshooting** - Hanya Task 2

```env
ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=false
ENABLE_TASK_2_PLC_READ=true
ENABLE_TASK_3_PROCESS_COMPLETED=false
ENABLE_TASK_4_HEALTH_MONITOR=false
```

**Hasil:** Hanya membaca data dari PLC untuk debugging.

---

### 4. **Batch Processing Only** - Task 1 & 3

```env
ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=true
ENABLE_TASK_2_PLC_READ=false
ENABLE_TASK_3_PROCESS_COMPLETED=true
ENABLE_TASK_4_HEALTH_MONITOR=false
```

**Hasil:** Sync MO dari Odoo dan process completed batches, tanpa real-time PLC read.

---

## 🔍 Monitoring Startup

Saat aplikasi start, akan terlihat di log:**

```
✓ Task 1: Auto-sync MO scheduler added (interval: 60 minutes)
✓ Task 2: PLC read sync scheduler added (interval: 5 minutes)
✓ Task 3: Process completed batches scheduler added (interval: 3 minutes)
✓ Task 4: Batch health monitoring scheduler added (interval: 10 minutes)

✓✓✓ Enhanced Scheduler STARTED with 4/4 tasks enabled ✓✓✓
  - Task 1: Auto-sync MO (60 min) - ✓
  - Task 2: PLC read sync (5 min) - ✓
  - Task 3: Process completed (3 min) - ✓
  - Task 4: Health monitoring (10 min) - ✓
```

Atau jika ada task yang disabled:

```
⊘ Task 2: PLC read sync scheduler DISABLED (ENABLE_TASK_2_PLC_READ=false)

✓✓✓ Enhanced Scheduler STARTED with 3/4 tasks enabled ✓✓✓
  - Task 1: Auto-sync MO (60 min) - ✓
  - Task 2: PLC read sync (5 min) - ⊘
  - Task 3: Process completed (3 min) - ✓
  - Task 4: Health monitoring (10 min) - ✓
```

---

## 📌 Important Notes

### Master Switch Behavior
- `ENABLE_AUTO_SYNC=false` akan **disable entire scheduler system** 
- Individual task flags hanya berlaku jika `ENABLE_AUTO_SYNC=true`

```env
# ❌ Jika ini false, semua task akan disabled terlepas dari setting individual
ENABLE_AUTO_SYNC=false

# ✓ Task-specific flags hanya berlaku jika ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=true  # Tidak akan aktif karena master switch false
```

### Default Values
- Semua task **enabled by default** (`true`)
- Jika tidak ada config, semua 4 task akan run dengan interval default

### Custom Intervals
- Interval dapat dikustomisasi per task
- Nilai minimum: 1 menit
- Nilai rekomendasi:
  - Task 1: 30-120 menit (data Odoo tidak berubah sering)
  - Task 2: 1-5 menit (real-time PLC read)
  - Task 3: 1-5 menit (process completed batches)
  - Task 4: 5-20 menit (health monitoring)

---

## 🚀 Common Scenarios

### Scenario A: Fast Development (Polling every 1 minute)

```env
ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=true
ENABLE_TASK_2_PLC_READ=true
ENABLE_TASK_3_PROCESS_COMPLETED=true
ENABLE_TASK_4_HEALTH_MONITOR=false

SYNC_INTERVAL_MINUTES=1
PLC_READ_INTERVAL_MINUTES=1
PROCESS_COMPLETED_INTERVAL_MINUTES=1
```

### Scenario B: Conservative (Longer intervals)

```env
ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=true
ENABLE_TASK_2_PLC_READ=true
ENABLE_TASK_3_PROCESS_COMPLETED=true
ENABLE_TASK_4_HEALTH_MONITOR=true

SYNC_INTERVAL_MINUTES=120
PLC_READ_INTERVAL_MINUTES=10
PROCESS_COMPLETED_INTERVAL_MINUTES=10
HEALTH_MONITOR_INTERVAL_MINUTES=20
```

### Scenario C: Selective (Hybrid approach)

```env
ENABLE_AUTO_SYNC=true
ENABLE_TASK_1_AUTO_SYNC=false      # Disable manual sync
ENABLE_TASK_2_PLC_READ=true
ENABLE_TASK_3_PROCESS_COMPLETED=true
ENABLE_TASK_4_HEALTH_MONITOR=true

PLC_READ_INTERVAL_MINUTES=2
PROCESS_COMPLETED_INTERVAL_MINUTES=2
HEALTH_MONITOR_INTERVAL_MINUTES=5
```

---

## 📝 Configuration Validation

Sistem akan **otomatis validate** konfigurasi saat startup:

- ✅ Setiap flag harus boolean (`true` atau `false`)
- ✅ Setiap interval harus integer > 0
- ✅ Invalid values akan raise error dan prevent startup

```python
# Contoh error jika konfigurasi invalid
ERROR: ENABLE_TASK_1_AUTO_SYNC must be boolean (got: 'yes')
ERROR: SYNC_INTERVAL_MINUTES must be positive integer (got: 0)
```

---

## 🔄 Managing Scheduler at Runtime

### Via API (Future Enhancement)

Dalam versi mendatang, akan ada endpoint untuk on/off tasks tanpa restart:

```bash
# Example (belum diimplementasi)
POST /api/scheduler/tasks/{task_id}/enable
POST /api/scheduler/tasks/{task_id}/disable
GET /api/scheduler/status
```

---

## 📚 Related Files

- **Config file:** `app/core/config.py` - Pydantic settings
- **Scheduler file:** `app/core/scheduler.py` - APScheduler setup
- **Log output:** Check startup logs untuk status setiap task

---

## ✅ Verification Checklist

- [ ] Ubah .env sesuai kebutuhan
- [ ] Restart aplikasi
- [ ] Check startup logs untuk confirm task status
- [ ] Monitor logs untuk verify task execution
- [ ] Test dengan mengubah interval untuk melihat polling behavior
- [ ] Validate tidak ada error messages

---

## 🆘 Troubleshooting

### 1. Task tidak jalan padahal enabled?

```
Login: Check ENABLE_AUTO_SYNC=true (master switch)
✓ Pastikan flag task specific juga true
✓ Check logs untuk error messages
✓ Verifikasi interval value valid (integer > 0)
```

### 2. Ada warning "DISABLED" di log padahal ingin enabled?

```
✓ Pastikan flag value benar: ENABLE_TASK_X=true (bukan Yes/1/on)
✓ Pastikan tidak ada whitespace: ENABLE_TASK_1_AUTO_SYNC = true ❌
✓ Correct format: ENABLE_TASK_1_AUTO_SYNC=true ✓
```

### 3. Sering ada timeout di Task X?

```
✓ Tingkatkan interval untuk reduce frequency
✓ Check PLC/Odoo connection stability
✓ Review query performance di logs
```

---

## 📞 Support

Jika ada pertanyaan, refer ke:
- Log file untuk error details
- `app/core/scheduler.py` untuk implementation details
- `app/core/config.py` untuk config structure
