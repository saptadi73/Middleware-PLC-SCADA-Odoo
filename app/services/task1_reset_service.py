import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_handshake_service import get_handshake_service
from app.services.plc_write_service import get_plc_write_service

logger = logging.getLogger(__name__)


class Task1ResetService:
    """Prepare TASK 1 to start from a clean initial state."""

    def __init__(self, db: Session):
        self.db = db
        self.handshake_service = get_handshake_service()
        self.plc_write_service = get_plc_write_service()

    def reset_for_fresh_start(self) -> dict[str, Any]:
        """
        Prepare TASK 1 fresh start by:
        1. Clearing existing PLC WRITE payloads
        2. Marking WRITE-area handshake flags as ready (status_read_data = 1)
        3. Clearing mo_batch table
        """
        cleared_slots = self.plc_write_service.clear_all_batch_slots()
        ready_addresses = self.handshake_service.mark_all_write_areas_as_ready()

        try:
            deleted_count = self.db.query(TableSmoBatch).delete(synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        logger.info(
            "TASK 1 fresh start prepared: cleared_write_slots=%s, write_ready_count=%s, deleted_mo_batch_count=%s",
            len(cleared_slots),
            len(ready_addresses),
            deleted_count,
        )

        return {
            "cleared_write_slots": cleared_slots,
            "cleared_write_slot_count": len(cleared_slots),
            "write_ready_addresses": [f"D{address}" for address in ready_addresses],
            "write_ready_count": len(ready_addresses),
            "deleted_mo_batch_count": deleted_count,
        }


def get_task1_reset_service(db: Session) -> Task1ResetService:
    """Factory for Task1ResetService."""
    return Task1ResetService(db)
