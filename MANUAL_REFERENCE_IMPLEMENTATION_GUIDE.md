# MANUAL_REFERENCE Implementation Guide

Status: Active
Updated: 2026-04-04

## Overview

Manual weighing sekarang menggunakan source reference baru: app/reference/MANUAL_REFERENCE.json.

Perubahan utama:
- Scheduler berjalan di Task 7 (bukan Task 5).
- Service membaca mapping MANUAL01 sampai MANUAL10.
- Default mode adalah ALL, jadi satu cycle akan scan semua slot.
- Handshake dilakukan per-slot sesuai address di setiap blok MANUALxx.

## Reference Structure

File reference:
- app/reference/MANUAL_REFERENCE.json

Setiap blok MANUALxx berisi field:
- BATCH
- NO-MO
- NO-Product
- Consumption
- status_manual_weigh_read

Contoh address per slot:
- MANUAL01: D9000..D9012 (handshake D9012)
- MANUAL02: D9100..D9112 (handshake D9112)
- ...
- MANUAL10: D9900..D9912 (handshake D9912)

## Environment Configuration

Gunakan variabel berikut di .env:

```env
ENABLE_TASK_7_MANUAL_WEIGHING=true
MANUAL_WEIGHING_INTERVAL_MINUTES=2
MANUAL_WEIGHING_REFERENCE_KEY=ALL
```

Nilai MANUAL_WEIGHING_REFERENCE_KEY:
- ALL: baca semua slot MANUAL01..MANUAL10 dalam satu cycle
- MANUAL01..MANUAL10: baca hanya satu slot tertentu

## Runtime Flow (Task 7)

1. Scheduler Task 7 trigger.
2. Service load layout dari MANUAL_REFERENCE.json sesuai mode key.
3. Untuk setiap layout:
- Read area DM sesuai rentang layout.
- Cek status_manual_weigh_read.
- Jika flag sudah 1, slot di-skip.
- Jika flag 0, data divalidasi lalu sync ke Odoo endpoint /api/scada/material-consumption.
- Jika sync sukses, handshake address slot tersebut di-set ke 1.
4. Cycle selesai, lanjut interval berikutnya.

## Files Related to Implementation

- app/core/config.py
- app/core/scheduler.py
- app/services/plc_manual_weighing_service.py
- app/services/plc_handshake_service.py
- app/reference/MANUAL_REFERENCE.json

## Notes

- .env tidak di-track ke GitHub, jadi perubahan mode key bersifat lokal per environment.
- Jika ingin cutover bertahap, set key ke satu slot dulu (misalnya MANUAL01), lalu pindah ke ALL setelah validasi.
