import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.tablesmo_batch import TableSmoBatch
from app.services.plc_handshake_service import get_handshake_service

logger = logging.getLogger(__name__)


class Task1ResetService:
    """Prepare TASK 1 to start from a clean initial state."""

    def __init__(self, db: Session):
        self.db = db
        self.handshake_service = get_handshake_service()

    def reset_for_fresh_start(self) -> dict[str, Any]:
        """
        Prepare TASK 1 fresh start by:
        1. Marking WRITE-area handshake flags as ready (status_read_data = 1)
        2. Clearing mo_batch table
        """
        ready_addresses = self.handshake_service.mark_all_write_areas_as_ready()

        try:
            deleted_count = self.db.query(TableSmoBatch).delete(synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        logger.info(
            "TASK 1 fresh start prepared: write_ready_count=%s, deleted_mo_batch_count=%s",
            len(ready_addresses),
            deleted_count,
        )

        return {
            "write_ready_addresses": [f"D{address}" for address in ready_addresses],
            "write_ready_count": len(ready_addresses),
            "deleted_mo_batch_count": deleted_count,
        }


def get_task1_reset_service(db: Session) -> Task1ResetService:
    """Factory for Task1ResetService."""
    return Task1ResetService(db)