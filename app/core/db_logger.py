import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.system_log import SystemLog


class DatabaseLogHandler(logging.Handler):
    """Logging handler that persists log records to table system_log."""

    def __init__(self, level: int = logging.NOTSET):
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("sqlalchemy"):
            return
        if record.name.startswith("uvicorn.access"):
            return

        session: Session = SessionLocal()
        try:
            msg = self.format(record)
            batch_no = getattr(record, "batch_no", None)
            mo_id = getattr(record, "mo_id", None)

            session.add(
                SystemLog(
                    level=str(record.levelname).upper(),
                    module=str(record.name),
                    message=msg,
                    batch_no=str(batch_no) if batch_no is not None else None,
                    mo_id=str(mo_id) if mo_id is not None else None,
                )
            )
            session.commit()
        except Exception:
            # Keep application logging robust; never crash due to DB log failure.
            pass
        finally:
            session.close()
