from __future__ import annotations

from app.core.database import SessionLocal
from app.services.plan_service import ensure_default_plans


def main() -> None:
    with SessionLocal() as db:
        ensure_default_plans(db)
    print("Default plans seeded.")


if __name__ == "__main__":
    main()
