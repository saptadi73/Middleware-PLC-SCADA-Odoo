"""
MO History Service

Service untuk manage history batch yang sudah selesai atau gagal.
Handle proses move dari mo_batch ke mo_histories setelah update ke Odoo.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.tablesmo_batch import TableSmoBatch
from app.models.tablesmo_history import TableSmoHistory

logger = logging.getLogger(__name__)


class MOHistoryService:
    """Service untuk manage MO histories"""

    def __init__(self, db: Session):
        self.db = db

    def _build_history_record(
        self,
        mo_batch: TableSmoBatch,
        status: str,
        notes: Optional[str],
    ) -> TableSmoHistory:
        """Build history record without persisting it."""
        return TableSmoHistory(
            batch_no=mo_batch.batch_no,
            mo_id=mo_batch.mo_id,
            consumption=mo_batch.consumption,
            equipment_id_batch=mo_batch.equipment_id_batch,
            finished_goods=mo_batch.finished_goods,
            # Silo IDs
            silo_a=mo_batch.silo_a,
            silo_b=mo_batch.silo_b,
            silo_c=mo_batch.silo_c,
            silo_d=mo_batch.silo_d,
            silo_e=mo_batch.silo_e,
            silo_f=mo_batch.silo_f,
            silo_g=mo_batch.silo_g,
            silo_h=mo_batch.silo_h,
            silo_i=mo_batch.silo_i,
            silo_j=mo_batch.silo_j,
            silo_k=mo_batch.silo_k,
            silo_l=mo_batch.silo_l,
            silo_m=mo_batch.silo_m,
            # Component names
            component_silo_a_name=mo_batch.component_silo_a_name,
            component_silo_b_name=mo_batch.component_silo_b_name,
            component_silo_c_name=mo_batch.component_silo_c_name,
            component_silo_d_name=mo_batch.component_silo_d_name,
            component_silo_e_name=mo_batch.component_silo_e_name,
            component_silo_f_name=mo_batch.component_silo_f_name,
            component_silo_g_name=mo_batch.component_silo_g_name,
            component_silo_h_name=mo_batch.component_silo_h_name,
            component_silo_i_name=mo_batch.component_silo_i_name,
            component_silo_j_name=mo_batch.component_silo_j_name,
            component_silo_k_name=mo_batch.component_silo_k_name,
            component_silo_l_name=mo_batch.component_silo_l_name,
            component_silo_m_name=mo_batch.component_silo_m_name,
            # Planned consumption
            consumption_silo_a=mo_batch.consumption_silo_a,
            consumption_silo_b=mo_batch.consumption_silo_b,
            consumption_silo_c=mo_batch.consumption_silo_c,
            consumption_silo_d=mo_batch.consumption_silo_d,
            consumption_silo_e=mo_batch.consumption_silo_e,
            consumption_silo_f=mo_batch.consumption_silo_f,
            consumption_silo_g=mo_batch.consumption_silo_g,
            consumption_silo_h=mo_batch.consumption_silo_h,
            consumption_silo_i=mo_batch.consumption_silo_i,
            consumption_silo_j=mo_batch.consumption_silo_j,
            consumption_silo_k=mo_batch.consumption_silo_k,
            consumption_silo_l=mo_batch.consumption_silo_l,
            consumption_silo_m=mo_batch.consumption_silo_m,
            # Actual consumption from PLC
            actual_consumption_silo_a=mo_batch.actual_consumption_silo_a,
            actual_consumption_silo_b=mo_batch.actual_consumption_silo_b,
            actual_consumption_silo_c=mo_batch.actual_consumption_silo_c,
            actual_consumption_silo_d=mo_batch.actual_consumption_silo_d,
            actual_consumption_silo_e=mo_batch.actual_consumption_silo_e,
            actual_consumption_silo_f=mo_batch.actual_consumption_silo_f,
            actual_consumption_silo_g=mo_batch.actual_consumption_silo_g,
            actual_consumption_silo_h=mo_batch.actual_consumption_silo_h,
            actual_consumption_silo_i=mo_batch.actual_consumption_silo_i,
            actual_consumption_silo_j=mo_batch.actual_consumption_silo_j,
            actual_consumption_silo_k=mo_batch.actual_consumption_silo_k,
            actual_consumption_silo_l=mo_batch.actual_consumption_silo_l,
            actual_consumption_silo_m=mo_batch.actual_consumption_silo_m,
            # Status
            status_manufacturing=mo_batch.status_manufacturing,
            status_operation=mo_batch.status_operation,
            actual_weight_quantity_finished_goods=mo_batch.actual_weight_quantity_finished_goods,
            last_read_from_plc=mo_batch.last_read_from_plc,
            # History metadata
            status=status,
            notes=notes,
        )

    def move_to_history(
        self,
        mo_batch: TableSmoBatch,
        status: str = "completed",
        notes: Optional[str] = None,
    ) -> Optional[TableSmoHistory]:
        """
        Move batch dari mo_batch ke mo_histories.

        Args:
            mo_batch: Record dari mo_batch yang akan dipindah
            status: Status history ("completed", "failed", "cancelled")
            notes: Catatan tambahan (optional)

        Returns:
            TableSmoHistory record jika berhasil, None jika gagal
        """
        try:
            history = self._build_history_record(mo_batch, status=status, notes=notes)

            self.db.add(history)
            self.db.commit()
            self.db.refresh(history)

            logger.info(
                f"✓ Moved MO {mo_batch.mo_id} (batch {mo_batch.batch_no}) "
                f"to history with status: {status}"
            )

            return history

        except Exception as e:
            logger.error(f"Error moving MO {mo_batch.mo_id} to history: {e}")
            self.db.rollback()
            return None

    def archive_batch(
        self,
        mo_batch: TableSmoBatch,
        status: str = "completed",
        notes: Optional[str] = None,
        mark_synced: bool = False,
    ) -> bool:
        """
        Archive batch ke history dan delete dari mo_batch dalam satu transaksi.

        Args:
            mo_batch: Record dari mo_batch yang akan di-archive
            status: Status history ("completed", "failed", "cancelled")
            notes: Catatan tambahan (optional)
            mark_synced: Jika True, set update_odoo=True sebelum delete

        Returns:
            True jika berhasil, False jika gagal
        """
        try:
            history = self._build_history_record(mo_batch, status=status, notes=notes)
            self.db.add(history)
            if mark_synced:
                mo_batch.update_odoo = True  # type: ignore
            self.db.delete(mo_batch)
            self.db.commit()

            logger.info(
                f"✓ Archived MO {mo_batch.mo_id} (batch {mo_batch.batch_no}) "
                f"to history with status: {status}"
            )
            return True

        except Exception as e:
            logger.error(f"Error archiving MO {mo_batch.mo_id} to history: {e}")
            self.db.rollback()
            return False

    def delete_from_batch(self, mo_batch: TableSmoBatch) -> bool:
        """
        Delete record dari mo_batch table.

        Args:
            mo_batch: Record yang akan dihapus

        Returns:
            True jika berhasil, False jika gagal
        """
        try:
            self.db.delete(mo_batch)
            self.db.commit()

            logger.info(
                f"✓ Deleted MO {mo_batch.mo_id} (batch {mo_batch.batch_no}) "
                "from mo_batch"
            )
            return True

        except Exception as e:
            logger.error(f"Error deleting MO {mo_batch.mo_id} from mo_batch: {e}")
            self.db.rollback()
            return False

    def cancel_batch(
        self,
        batch_no: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cancel a batch dan pindahkan ke history dengan status 'cancelled'.
        
        Digunakan untuk batch yang gagal atau tidak jadi diproses dan tidak perlu diulang.
        Batch akan dihapus dari mo_batch dan disimpan ke mo_histories dengan status cancelled.

        Args:
            batch_no: Nomor batch yang akan di-cancel
            notes: Alasan cancellation (optional)

        Returns:
            Dict dengan info hasil cancellation
        """
        try:
            # Cari batch berdasarkan batch_no
            stmt = select(TableSmoBatch).where(
                TableSmoBatch.batch_no == batch_no
            )
            result = self.db.execute(stmt)
            batch = result.scalar_one_or_none()

            if not batch:
                logger.warning(f"Batch {batch_no} not found in mo_batch")
                return {
                    "success": False,
                    "message": f"Batch {batch_no} not found",
                }

            mo_id = batch.mo_id
            
            archived = self.archive_batch(
                batch,
                status="cancelled",
                notes=notes or "Manually cancelled by operator",
                mark_synced=False,
            )

            if not archived:
                return {
                    "success": False,
                    "message": f"Failed to archive cancelled batch {batch_no}",
                }

            logger.info(
                f"✓ Cancelled batch {batch_no} (MO: {mo_id}) "
                f"and moved to history"
            )

            return {
                "success": True,
                "message": f"Batch {batch_no} cancelled successfully",
                "batch_no": batch_no,
                "mo_id": mo_id,
                "status": "cancelled",
            }

        except Exception as e:
            logger.error(f"Error cancelling batch {batch_no}: {e}")
            self.db.rollback()
            return {
                "success": False,
                "message": f"Error cancelling batch: {str(e)}",
            }

    def get_completed_batches(self) -> List[TableSmoBatch]:
        """
        Get all completed batches (status_manufacturing = 1).

        Returns:
            List of completed batch records
        """
        try:
            stmt = select(TableSmoBatch).where(
                TableSmoBatch.status_manufacturing.is_(True)
            )
            result = self.db.execute(stmt)
            batches = result.scalars().all()

            logger.info(f"Found {len(batches)} completed batches")
            return list(batches)

        except Exception as e:
            logger.error(f"Error getting completed batches: {e}")
            return []

    def get_failed_batches(self) -> List[TableSmoBatch]:
        """
        Get all failed batches.

        Failure is represented by:
        - status_operation = 1 (failed)
        - status_manufacturing = 0 (not completed)

        Returns:
            List of failed batch records
        """
        try:
            stmt = select(TableSmoBatch).where(
                and_(
                    TableSmoBatch.status_operation.is_(True),
                    TableSmoBatch.status_manufacturing.is_(False),
                )
            )
            result = self.db.execute(stmt)
            batches = result.scalars().all()

            logger.info(f"Found {len(batches)} failed batches")
            return list(batches)

        except Exception as e:
            logger.error(f"Error getting failed batches: {e}")
            return []

    def get_history(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[TableSmoHistory]:
        """
        Get history records dengan pagination.

        Args:
            limit: Maximum records to return
            offset: Offset for pagination
            status: Filter by status (optional)

        Returns:
            List of history records
        """
        try:
            stmt = select(TableSmoHistory).order_by(
                TableSmoHistory.last_read_from_plc.desc()
            )

            # Filter by status if provided
            if status:
                stmt = stmt.where(TableSmoHistory.status == status)

            stmt = stmt.limit(limit).offset(offset)

            result = self.db.execute(stmt)
            histories = result.scalars().all()

            logger.info(f"Retrieved {len(histories)} history records")
            return list(histories)

        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []

    def get_history_by_mo_id(self, mo_id: str) -> Optional[TableSmoHistory]:
        """
        Get history record by MO ID.

        Args:
            mo_id: MO ID to search

        Returns:
            History record if found, None otherwise
        """
        try:
            stmt = select(TableSmoHistory).where(
                TableSmoHistory.mo_id == mo_id
            )
            result = self.db.execute(stmt)
            history = result.scalar_one_or_none()

            return history

        except Exception as e:
            logger.error(f"Error getting history for MO {mo_id}: {e}")
            return None


# Singleton instance
_mo_history_service: Optional[MOHistoryService] = None


def get_mo_history_service(db: Session) -> MOHistoryService:
    """Get MOHistoryService instance"""
    return MOHistoryService(db=db)
