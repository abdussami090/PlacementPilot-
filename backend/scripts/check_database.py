"""Check that the configured PlacementPilot database accepts connections."""

from sqlalchemy import text

from app.database import DATABASE_URL, engine


def main() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        print(f"Database connection successful: {safe_url}")
    except Exception as exc:
        print(f"Database connection failed: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
