import logging

from sqlalchemy.exc import SQLAlchemyError

from app.database.session import SessionLocal
from app.models.users import User  # Register the users table in Base.metadata.
from app.services.skill_catalog_service import seed_skill_catalog

logger = logging.getLogger(__name__)


def seed_catalog_on_startup() -> None:
    """Ortak beceri kataloğunu her açılışta tamamlar; zaten olan kayıtlara dokunmaz.

    Katalog boş kalırsa profilde ve ilanlarda seçilecek beceri çıkmaz. Elle çalıştırılan
    seed adımı unutulabildiği için uygulama bunu kendisi yapar. Tablolar henüz yoksa
    (migration çalışmadıysa) uygulama yine açılır, yalnızca uyarı yazılır.
    """
    db = SessionLocal()
    try:
        result = seed_skill_catalog(db)
    except SQLAlchemyError:
        logger.warning(
            "Skill catalog could not be seeded at startup; run 'alembic upgrade head' first."
        )
        return
    finally:
        db.close()
    if result["skills_created"] or result["aliases_created"]:
        logger.warning(
            "Skill catalog updated: %s skills, %s aliases added.",
            result["skills_created"],
            result["aliases_created"],
        )


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_skill_catalog(db)
        print(
            "Skill catalog seeded: "
            f"{result['skills_created']} skills, "
            f"{result['aliases_created']} aliases added."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
