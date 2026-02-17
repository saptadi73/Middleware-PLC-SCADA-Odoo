import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.system_log import SystemLog
import traceback

class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler that writes logs to the database.
    """
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        # Skip logs from sqlalchemy engine to prevent infinite loops
        if record.name.startswith("sqlalchemy"):
            return
            
        # Skip uvicorn access logs if needed (too noisy)
        if "uvicorn.access" in record.name:
            return

        session: Session = SessionLocal()
        try:
            # Format message
            msg = self.format(record)
            
            # Extract extra fields if passed in extra={}
            batch_no = getattr(record, 'batch_no', None)
            mo_id = getattr(record, 'mo_id', None)

            log_entry = SystemLog(
                level=record.levelname,
                module=record.name,
                message=msg,
                batch_no=str(batch_no) if batch_no else None,
                mo_id=str(mo_id) if mo_id else None
            )
            
            session.add(log_entry)
            session.commit()
        except Exception:
            # If logging fails, fallback to stderr so we don't crash the app
            # and don't create infinite logging loops
            pass
        finally:
            session.close()