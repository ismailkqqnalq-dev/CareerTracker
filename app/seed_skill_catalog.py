from app.database.session import SessionLocal
from app.models.users import User  # Register the users table in Base.metadata.
from app.services.skill_catalog_service import seed_skill_catalog


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
