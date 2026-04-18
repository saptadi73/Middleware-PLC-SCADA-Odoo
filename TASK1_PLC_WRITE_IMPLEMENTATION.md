# TASK 1 Updated - With PLC WRITE Implementation

## Confirmed

TASK 1 memang harus menulis MO confirm dari Odoo ke PLC, karena PLC mengeksekusi batch dari WRITE memory dan Task 2 membaca hasil eksekusinya dari READ memory.

## Task 1 Flow

1. Cek `mo_batch` kosong atau tidak.
2. Jika kosong, fetch daftar MO confirm dari Odoo.
3. Stage atau update semua MO hasil fetch ke `mo_batch` dengan deferred commit.
4. Dalam cycle yang sama, segera tulis semua batch hasil fetch ke PLC WRITE area slot `1..N`.
5. Commit `mo_batch` hanya jika seluruh penulisan ke PLC sukses penuh.
6. Jika write PLC gagal, rollback stage database agar DB tidak tertinggal dari state PLC.

## Implemented Behavior

- Scheduler memanggil `sync_mo_list_to_db(..., commit=False)` lebih dulu.
- Setelah itu scheduler memanggil `write_mo_batch_queue_to_plc(...)`.
- Final `db.commit()` hanya dilakukan jika jumlah batch yang berhasil ditulis ke PLC sama dengan jumlah batch yang di-stage.

## Important Note

Urutan yang benar bukan:

`fetch Odoo -> commit DB -> write PLC`

Urutan yang dipakai sekarang adalah:

`fetch Odoo -> stage mo_batch -> write semua ke PLC -> commit DB`

Urutan ini menjaga konsistensi agar `mo_batch` tidak committed bila penulisan PLC gagal di tengah jalan.

## Safety Notes

- Task 1 hanya berjalan saat `mo_batch` kosong.
- Handshake WRITE slot dipakai untuk mencegah overwrite data yang belum dibaca PLC.
- Bila satu slot belum ready, cycle write dianggap belum aman untuk diselesaikan.
- Bila write gagal sebelum final commit, perubahan `mo_batch` di-rollback.

## Verification Target

Log sukses Task 1 idealnya memperlihatkan urutan ini:

1. Odoo mengembalikan `N` MO.
2. `mo_batch` stage selesai untuk `N` MO.
3. PLC write selesai untuk `N` batch.
4. Commit database sukses untuk `N` batch.
