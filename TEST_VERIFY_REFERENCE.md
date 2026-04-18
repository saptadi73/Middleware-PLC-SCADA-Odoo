# Test And Verify Script Reference

Status: canonical review
Reviewed on: 2026-04-18
Scope: all `test_*.py`, `verify_*.py`, and `tools/verify*.py`

## Purpose

Dokumen ini adalah acuan utama untuk memilih script test/verify yang sudah ada di repo ini.
Tujuannya:

- menghindari penulisan script baru untuk kasus yang sebenarnya sudah tercakup,
- membedakan script yang masih sesuai desain final vs script historis,
- menyamakan interpretasi test dengan konfigurasi dan mapping yang aktif saat ini.

## Source Of Truth

Saat menilai validitas script, source of truth yang dipakai adalah:

- `app/core/config.py`
- `app/core/scheduler.py`
- `app/reference/MASTER_BATCH_REFERENCE.json`
- `app/reference/READ_DATA_PLC_MAPPING.json`
- `app/reference/MANUAL_REFERENCE.json`
- `app/reference/EQUIPMENT_FAILURE_REFERENCE.json`

Catatan penting:

- Jangan jadikan `.env.example` sebagai sumber kebenaran final. File itu masih memuat beberapa nama env var lama.
- Jangan jadikan `MANUAL_REFERENCE_IMPLEMENTATION_GUIDE.md` sebagai sumber kebenaran final untuk layout manual weighing. Dokumen itu masih menyebut layout per blok lama, sedangkan file aktif sekarang adalah `MANUAL_REFERENCE.json` dengan slot padat `D9000-D9048`.
- Scheduler final di code memiliki 7 task:
  1. Task 1: auto sync Odoo -> DB -> PLC write
  2. Task 2: PLC read -> update `mo_batch`
  3. Task 3: process completed -> sync Odoo -> archive
  4. Task 4: health monitor
  5. Task 5: manual weighing
  6. Task 6: log cleanup
  7. Task 7: equipment failure

## Execution Baseline

Interpreter yang tervalidasi untuk repo ini adalah:

```powershell
venv\Scripts\python.exe
```

Catatan lingkungan saat review:

- `venv\Scripts\python.exe` dapat mengimpor dependency repo dengan benar.
- `.venv\Scripts\python.exe` tidak usable pada environment saat review.
- `test_db_connection.py` gagal di environment saat review karena kredensial Postgres pada `.env` ditolak:
  `postgresql+psycopg2://plc:***@localhost:5432/plc`

## Validation Performed

Validasi yang dilakukan saat review ini:

- semua script lulus `py_compile` (syntax level),
- import audit memakai `venv\Scripts\python.exe`,
- eksekusi aman untuk script non-destructive berikut:
  - `test_scheduler_config.py`
  - `test_manual_weighing_workflow.py`
  - `verify_data_type_handling.py`
  - `verify_lq_config.py`
  - `verify_additional_equipment.py`
  - `verify_additional_equipment_updated.py`
  - `test_db_connection.py`
- pengecekan CLI help:
  - `test_fins_udp_diagnostic.py --help`
  - `test_get_mo_list_odoo.py --help`
  - `test_manual_weighing_read_only.py --help`
  - `tools/verify_task1_lq_write_area.py --help`

## Status Legend

- `Recommended`: sesuai desain final dan layak jadi rujukan utama.
- `Valid`: masih benar dan berguna, tetapi lebih sempit atau lebih teknis.
- `Limited`: masih bisa dipakai, tetapi narasi/cakupannya sudah tidak lengkap.
- `Legacy`: hanya relevan untuk fallback lama atau artefak historis.
- `Do not use`: bertentangan dengan code/config final atau memberi hasil yang menyesatkan.

## Quick Lookup

| Need | Use This First |
|---|---|
| Cek koneksi database | `test_db_connection.py` |
| Cek koneksi PLC dasar | `test_plc_connection.py` |
| Diagnosis node/bind FINS | `test_fins_udp_diagnostic.py` |
| Cek daftar MO dari Odoo sebelum Task 1 | `test_get_mo_list_odoo.py` |
| Task 1 tanpa PLC write | `test_task1_odoo_to_postgres.py` |
| Task 1 full sampai PLC write | `test_task1_with_plc_write.py` |
| Verifikasi LQ114/LQ115 di write area | `tools/verify_task1_lq_write_area.py` |
| Simulasi READ area dari CSV | `test_write_read_area_from_csv.py` |
| Simulasi READ area dari Odoo | `test_write_read_area_from_odoo.py` |
| Dump READ area ke CSV/XLSX | `test_export_read_area_to_csv.py` |
| Decode lengkap BATCH01 READ area | `test_batch01_read_d6000_6076.py` |
| Jalankan Task 2 sesuai desain final | `test_task2_plc_read_sync.py` |
| Jalankan Task 3 sesuai desain final | `test_task3_process_completed.py` |
| Manual weighing read-only | `test_manual_weighing_read_only.py` |
| Unit test workflow manual weighing | `test_manual_weighing_workflow.py` |
| Equipment failure PLC read/write | `test_equipment_failure_read.py`, `test_equipment_failure_write.py` |
| Equipment failure sync ke Odoo | `test_equipment_failure_odoo_sync.py` |
| Konsistensi data type antar service | `verify_data_type_handling.py` |

## Inventory

### 1. Environment And Connectivity

| Script | Purpose | Status | Notes |
|---|---|---|---|
| `test_db_connection.py` | Smoke test koneksi database via `SessionLocal` | Recommended | Saat review gagal karena auth Postgres pada `.env`; script-nya sendiri masih benar |
| `verify_migration.py` | Verifikasi kolom/index hasil migrasi `mo_histories` | Valid | Berguna saat audit schema; saat review gagal karena DB auth environment |
| `test_plc_connection.py` | Read-only FINS UDP reachability test | Recommended | Paling aman untuk cek PLC sebelum test lain |
| `test_fins_udp_diagnostic.py` | Matrix diagnostic untuk node, DA2, bind mode, local IP | Recommended | Gunakan saat `test_plc_connection.py` timeout atau salah node |
| `test_get_mo_list_odoo.py` | Pre-check MO list dari Odoo sebelum Task 1 | Recommended | Tidak menulis DB/PLC |
| `test_odoo_mo_list.py` | Direct JSON-RPC ke Odoo `mrp.production` | Valid | Bypass kontrak middleware; cocok untuk isolasi masalah Odoo |
| `test_mo_sync.py` | Panggil endpoint middleware `/api/scada/mo-list-detailed` lalu cek DB | Valid | Butuh server API + DB |
| `test_scheduler.py` | Verifikasi gate Task 1 berbasis jumlah row `mo_batch` | Limited | Hanya membahas auto-sync lama, belum 7 task final |
| `test_scheduler_config.py` | Ringkasan flag scheduler dari env | Limited | Saat review lulus, tetapi hanya melaporkan Task 1-4 dan mengabaikan Task 5-7 |

### 2. Task 1 And PLC WRITE Area

| Script | Purpose | Status | Notes |
|---|---|---|---|
| `test_task1_odoo_to_postgres.py` | Task 1 tahap fetch Odoo -> stage DB saja | Recommended | Cocok untuk verifikasi data Odoo tanpa PLC write |
| `test_task1_with_plc_write.py` | Task 1 full: fetch -> stage -> PLC write -> commit | Recommended | Ini script acuan utama untuk Task 1 final |
| `test_task1_with_plc_write_no_handshake_check.py` | Sama seperti di atas tetapi bypass pre-handshake | Valid | Hanya untuk lab/debug saat handshake menghalangi write |
| `test_task1_smart_sync.py` | Cek logika queue kosong/busy | Limited | Tidak memverifikasi write ke PLC atau atomic commit final |
| `test_plc_write.py` | Smoke test endpoint `/api/plc/write-*` | Valid | Cocok untuk API middleware, bukan untuk flow Task 1 penuh |
| `test_plc_write_from_odoo.py` | Ambil data Odoo lalu tulis langsung ke PLC | Valid | Bypass scheduler dan staging final; bagus untuk eksperimen |
| `test_dummy_mapping_d10000.py` | Tulis payload dummy ke area uji `D10000` | Valid | Tool lab terisolasi, bukan write area produksi |
| `tools/verify_task1_lq_write_area.py` | Verifikasi field LQ114/LQ115 di write area Task 1 | Recommended | Sangat berguna sesudah `test_task1_with_plc_write.py` |
| `test_handshake.py` | Verifikasi handshake READ/WRITE/equipment failure | Recommended | Tetap relevan dengan desain final |

### 3. PLC READ Area, Simulation, And Raw Inspection

| Script | Purpose | Status | Notes |
|---|---|---|---|
| `test_plc_read.py` | Smoke test endpoint read PLC via middleware API | Valid | Masih sesuai route saat ini |
| `test_plc_read_direct.py` | Direct read via `PLCReadService` tanpa HTTP | Recommended | Acuan terbaik untuk cek decoding service |
| `test_plc_read_quick.py` | Quick snapshot/debug read | Valid | Ringan untuk inspeksi cepat |
| `test_plc_read_update_odoo.py` | Read PLC lalu update Odoo di luar flow resmi | Limited | Berguna sebagai debug ad-hoc, tetapi mencampur boundary Task 2/3 |
| `test_plc_sync.py` | Smoke test endpoint `/api/plc/sync-from-plc` | Valid | Cocok untuk cek integrasi read -> DB |
| `test_complete_cycle.py` | Loop write -> read -> sync via API | Valid | Masih berguna, tetapi narasi dependensi test masih manual |
| `test_plc_workflow.py` | Workflow API gabungan untuk PLC | Valid | Helper historis yang masih bisa dipakai |
| `test_write_read_area.py` | Tulis batch DB ke READ area memakai mapping aktif | Recommended | Baik untuk simulasi PLC feedback |
| `test_write_read_area_from_csv.py` | Tulis READ area dari CSV input | Recommended | Cocok untuk replay skenario tertentu |
| `test_write_read_area_from_odoo.py` | Tulis READ area dari live Odoo MO list | Recommended | Sudah mendukung 13 silo + LQ114/LQ115 |
| `test_export_read_area_to_csv.py` | Export snapshot READ area ke CSV | Recommended | Bagus untuk bukti lapangan dan diff snapshot |
| `test_batch01_read_d6000_6076.py` | Decode lengkap BATCH01 `D6000-D6076` | Recommended | Paling detail untuk inspeksi word-by-word |
| `verify_silo_a_consumption.py` | Verifikasi khusus decoding `silo_a` | Valid | Narrow regression helper |

Catatan penting untuk section ini:

- Range final BATCH01 adalah `D6000-D6076`.
- Beberapa banner/docstring lama masih menulis `D6001-D6076`.
- Secara operasional script tetap benar selama ia load mapping dari `READ_DATA_PLC_MAPPING.json`.

### 4. Task 2, Task 3, And Odoo Consumption

| Script | Purpose | Status | Notes |
|---|---|---|---|
| `test_task2_plc_read_sync.py` | Jalankan `plc_read_sync_task()` sesuai desain final | Recommended | Script acuan Task 2 |
| `test_task2_debug.py` | Debug mendalam Task 2 lalu manual sync ke Odoo | Limited | Deskripsinya masih menyiratkan Task 2 sync Odoo, padahal final flow memisahkan Odoo ke Task 3 |
| `test_task2_write_active_mo.py` | Menyiapkan payload active batch untuk analisis | Limited | Nama file menyesatkan; script tidak benar-benar menulis ke PLC |
| `test_task3_process_completed.py` | Jalankan `process_completed_batches_task()` | Recommended | Script acuan Task 3 final |
| `test_task3_live.py` | Replay manual `process_batch_consumption()` untuk MO tertentu | Recommended | Cocok untuk investigasi Odoo sync per MO |
| `test_odoo_consumption.py` | Contoh service-level untuk mapping/update/mark-done | Valid | Hanya test mapping yang aktif default; test Odoo nyata masih di-comment |
| `test_quantity_payload.py` | Verifikasi payload quantity ke Odoo | Valid | Bagus untuk cek field `actual_weight_quantity_finished_goods` |
| `test_mo_batch_process.py` | End-to-end lama dengan helper direct move-to-history | Limited | Tidak merefleksikan safety path final Task 3 secara penuh |

### 5. Manual Weighing

| Script | Purpose | Status | Notes |
|---|---|---|---|
| `test_manual_weighing_read_only.py` | Read-only scan manual weighing + export CSV/XLSX | Recommended | Acuan utama manual weighing final |
| `test_manual_weighing_workflow.py` | Unit test handshake/order-of-operations | Recommended | Saat review: 4 test pass |
| `verify_additional_equipment.py` | Inspeksi file fallback `ADDITIONAL_EQUIPMENT_REFERENCE.json` | Legacy | Hanya relevan jika fallback legacy dipakai |
| `verify_additional_equipment_updated.py` | Validasi layout ADDITIONAL versi lama | Do not use | Saat review menghasilkan error karena ekspektasi layout sudah tidak sesuai file aktif |
| `test_additional_equipment_comprehensive.py` | Validasi komprehensif layout ADDITIONAL lama | Do not use | Mengasumsikan layout dan word model yang sudah tidak sama dengan desain final |

Catatan penting untuk manual weighing final:

- Path aktif adalah `app/reference/MANUAL_REFERENCE.json`.
- Layout aktif sekarang adalah slot padat `D9000-D9048`, bukan blok lama satu slot per rentang besar.
- Service memuat slot `SLOT01..SLOT10` dari `MANUAL_REFERENCE.json`.
- `ADDITIONAL_EQUIPMENT_REFERENCE.json` sekarang statusnya fallback legacy, bukan referensi utama.

### 6. Equipment Failure

| Script | Purpose | Status | Notes |
|---|---|---|---|
| `test_equipment_failure_write.py` | Tulis payload equipment failure ke PLC | Recommended | Masih sesuai reference aktif |
| `test_equipment_failure_read.py` | Baca payload equipment failure dari PLC | Recommended | Masih sesuai reference aktif |
| `test_equipment_failure_odoo_sync.py` | Uji auth Odoo + endpoint equipment failure | Recommended | Sudah pakai endpoint final `/api/scada/equipment-failure` |

### 7. Static Mapping And Data-Type Regression

| Script | Purpose | Status | Notes |
|---|---|---|---|
| `verify_data_type_handling.py` | Cek konsistensi convert REAL/INT antar service | Recommended | Saat review lulus |
| `verify_lq_config.py` | Cek konfigurasi LQ114/LQ115 di `silo_data.json` | Recommended | Saat review lulus |
| `test_comprehensive_unsigned_fix.py` | Regression test untuk unsigned REAL handling | Valid | Spesifik kasus historis, tetap berguna |
| `test_unsigned_fix.py` | Regression helper sederhana untuk unsigned conversion | Valid | Narrow helper |
| `test_silo_ab_fix.py` | Cek konsistensi mapping silo A/B | Valid | Masih berguna sebagai static regression |

### 8. Historical Scripts That Should Not Be Used As Canonical Reference

| Script | Why It Is Outdated | Status |
|---|---|---|
| `test_consumption_flow_fixed.py` | Import `app.db.database` sudah tidak ada, pakai nama class lama `PlcSyncService`/`PlcReadService`, dan memanggil method async `_update_batch_if_changed()` secara sinkron | Do not use |
| `test_consumption_after_completion.py` | Memanggil method async `_update_batch_if_changed()` tanpa `await`, sehingga tidak lagi mencerminkan perilaku service final | Do not use |
| `test_two_cycle_status_flow.py` | Import `PlcSyncService` sudah invalid dan logika yang diuji tidak lagi selaras dengan service final | Do not use |
| `test_full_plc_to_odoo.py` | Masih memakai atribut `settings.odoo_user` yang tidak ada, hardcoded Linux path, dan memanggil `_update_batch_if_changed()` secara salah | Do not use |
| `test_read_plc_to_odoo.py` | Hardcoded Linux path, memanggil `_update_batch_if_changed()` secara salah, dan mencampur boundary service lama | Do not use |
| `test_full_cycle_live.py` | Mengasumsikan Task 3 memproses batch dengan `update_odoo=True`, padahal filter final Task 3 adalah `status_manufacturing=True AND update_odoo=False` | Do not use |
| `test_live_complete_cycle.py` | Mengasumsikan Task 2 melakukan sync Odoo lalu set `update_odoo=True`; itu bukan flow final | Do not use |
| `test_task2_task3_with_real_data.py` | Sama seperti di atas: asumsi bahwa Task 2 sync Odoo dan menyalakan `update_odoo` | Do not use |

## Canonical Minimal Test Pack

Jika tim hanya ingin mempertahankan satu set acuan kecil tanpa menulis script baru, gunakan urutan ini:

1. `venv\Scripts\python.exe test_db_connection.py`
2. `venv\Scripts\python.exe test_plc_connection.py`
3. `venv\Scripts\python.exe test_get_mo_list_odoo.py --save-json snapshots/odoo_mo_precheck_latest.json`
4. `venv\Scripts\python.exe test_task1_odoo_to_postgres.py`
5. `venv\Scripts\python.exe test_task1_with_plc_write.py`
6. `venv\Scripts\python.exe tools/verify_task1_lq_write_area.py`
7. `venv\Scripts\python.exe test_task2_plc_read_sync.py`
8. `venv\Scripts\python.exe test_task3_process_completed.py`
9. `venv\Scripts\python.exe test_manual_weighing_read_only.py --slot 1`
10. `venv\Scripts\python.exe -m unittest test_manual_weighing_workflow.py`
11. `venv\Scripts\python.exe test_equipment_failure_read.py`
12. `venv\Scripts\python.exe test_equipment_failure_write.py`
13. `venv\Scripts\python.exe test_equipment_failure_odoo_sync.py`
14. `venv\Scripts\python.exe verify_data_type_handling.py`

## Recommended Rules Going Forward

- Untuk validasi desain final, utamakan script berstatus `Recommended`.
- Untuk investigasi lokal cepat, script berstatus `Valid` masih aman dipakai.
- Jangan gunakan script berstatus `Do not use` sebagai bukti regresi atau referensi SOP.
- Jika ada konflik antara dokumen lama dan perilaku code, ikuti `config.py`, `scheduler.py`, dan reference JSON aktif.
- Jika butuh simulasi manual weighing, pakai `test_manual_weighing_read_only.py`, bukan script ADDITIONAL legacy.
- Jika butuh verifikasi Task 2/Task 3, jangan pakai script yang mengasumsikan Task 2 melakukan Odoo sync.
