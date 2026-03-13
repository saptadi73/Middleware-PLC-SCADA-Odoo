import logging
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tablesmo_batch import TableSmoBatch
from app.models.tablesmo_history import TableSmoHistory

logger = logging.getLogger(__name__)


class TableViewService:
    """Service untuk menampilkan data tabel mo_batch dan mo_histories."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _serialize_mo_batch(row: TableSmoBatch) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "batch_no": row.batch_no,
            "mo_id": row.mo_id,
            "equipment_id_batch": row.equipment_id_batch,
            "finished_goods": row.finished_goods,
            "consumption": float(row.consumption) if row.consumption is not None else 0.0,
            "status_manufacturing": bool(row.status_manufacturing),
            "status_operation": bool(row.status_operation),
            "actual_weight_quantity_finished_goods": (
                float(row.actual_weight_quantity_finished_goods)
                if row.actual_weight_quantity_finished_goods is not None
                else 0.0
            ),
            "last_read_from_plc": (
                row.last_read_from_plc.isoformat() if row.last_read_from_plc is not None else None
            ),
            "update_odoo": bool(row.update_odoo),
        }

    @staticmethod
    def _serialize_mo_history(row: TableSmoHistory) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "batch_no": row.batch_no,
            "mo_id": row.mo_id,
            "equipment_id_batch": row.equipment_id_batch,
            "finished_goods": row.finished_goods,
            "consumption": float(row.consumption) if row.consumption is not None else 0.0,
            "status_manufacturing": bool(row.status_manufacturing),
            "status_operation": bool(row.status_operation),
            "actual_weight_quantity_finished_goods": (
                float(row.actual_weight_quantity_finished_goods)
                if row.actual_weight_quantity_finished_goods is not None
                else 0.0
            ),
            "last_read_from_plc": (
                row.last_read_from_plc.isoformat() if row.last_read_from_plc is not None else None
            ),
            "status": row.status,
            "notes": row.notes,
        }

    def get_mo_batch_table(self) -> dict[str, Any]:
        """Ambil semua data mo_batch untuk tampilan tabel."""
        stmt = select(TableSmoBatch).order_by(TableSmoBatch.batch_no.asc())
        result = self.db.execute(stmt)
        rows = result.scalars().all()

        logger.info("Retrieved %s row(s) from mo_batch", len(rows))

        return {
            "total": len(rows),
            "items": [self._serialize_mo_batch(row) for row in rows],
        }

    def get_mo_histories_table(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        mo_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Ambil data mo_histories dengan pagination."""
        base_stmt = select(TableSmoHistory)
        count_stmt = select(func.count()).select_from(TableSmoHistory)

        if status:
            base_stmt = base_stmt.where(TableSmoHistory.status == status)
            count_stmt = count_stmt.where(TableSmoHistory.status == status)

        if mo_id:
            base_stmt = base_stmt.where(TableSmoHistory.mo_id.ilike(f"%{mo_id}%"))
            count_stmt = count_stmt.where(TableSmoHistory.mo_id.ilike(f"%{mo_id}%"))

        total = self.db.execute(count_stmt).scalar_one()

        stmt = (
            base_stmt
            .order_by(TableSmoHistory.last_read_from_plc.desc().nullslast())
            .limit(limit)
            .offset(offset)
        )
        result = self.db.execute(stmt)
        rows = result.scalars().all()

        logger.info(
            (
                "Retrieved %s history row(s) from mo_histories "
                "(limit=%s offset=%s status=%s mo_id=%s)"
            ),
            len(rows),
            limit,
            offset,
            status,
            mo_id,
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": (offset + len(rows)) < total,
            "items": [self._serialize_mo_history(row) for row in rows],
        }


def get_table_view_service(db: Session) -> TableViewService:
    return TableViewService(db=db)
