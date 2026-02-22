from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.core.config import get_settings


def _mask_database_url(database_url: str) -> str:
    if "@" not in database_url or "://" not in database_url:
        return database_url

    scheme, rest = database_url.split("://", 1)
    if "@" not in rest:
        return database_url

    credentials, host_part = rest.split("@", 1)
    if ":" in credentials:
        username = credentials.split(":", 1)[0]
        return f"{scheme}://{username}:***@{host_part}"

    return f"{scheme}://***@{host_part}"


def main() -> int:
    settings = get_settings()
    print("=" * 70)
    print("DATABASE CONNECTION TEST")
    print("=" * 70)
    print(f"Database URL: {_mask_database_url(settings.database_url)}")

    db = SessionLocal()
    try:
        result = db.execute(text("SELECT 1"))
        value = result.scalar()

        if value == 1:
            print("\n✅ SUCCESS: Database connection is working.")
            return 0

        print(f"\n⚠️ Unexpected query result: {value}")
        return 1
    except SQLAlchemyError as error:
        print(f"\n❌ FAILED: Cannot connect to database.\n{error}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
