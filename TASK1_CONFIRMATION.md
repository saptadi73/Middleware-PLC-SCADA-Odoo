# TASK 1 - PLC WRITE Implementation Confirmation

## Requirement

TASK 1 harus:

1. mengambil daftar MO confirm dari Odoo,
2. memperbarui `mo_batch`,
3. segera menuliskan seluruh batch hasil fetch ke PLC,
4. lalu memfinalkan commit database hanya jika write PLC sukses penuh.

## Confirmed Flow

Before:

`fetch Odoo -> save DB -> return`

Current implemented flow:

`fetch Odoo -> stage mo_batch -> write semua batch ke PLC -> commit DB`

## Why This Flow Is Used

- PLC membutuhkan instruksi batch di WRITE memory.
- Middleware membutuhkan `mo_batch` sebagai queue kerja internal.
- Commit database ditunda sampai PLC write sukses agar DB dan PLC tidak mudah mismatch.

## Atomicity Rule

1. Stage/update `mo_batch` dulu.
2. Tulis semua batch hasil fetch ke PLC slot `1..N`.
3. Jika seluruh write sukses, commit `mo_batch`.
4. Jika ada write gagal, rollback perubahan database cycle tersebut.

## Operational Note

Istilah "setelah berhasil update table MO Batch" di implementasi saat ini berarti:

- data sudah berhasil di-stage atau di-update pada session database,
- tetapi belum final commit,
- lalu langsung dipakai untuk menulis seluruh queue ke PLC dalam cycle yang sama.

## Expected Log Pattern

Urutan log yang benar:

1. `Found N MO(s) from Odoo`
2. `Database stage completed (not committed yet): N MO batches`
3. `PLC write completed: N batches written to PLC`
4. `Auto-sync committed successfully: staged=N, written=N`

Jika yang muncul hanya sampai langkah 2, berarti penulisan PLC belum selesai sukses.
