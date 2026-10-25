from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os
load_dotenv()

database_url = os.getenv("DATABASE_URL", "sqlite:///careertracker.db")


def create_database_engine(url: str, **engine_options):
    if not url.startswith("sqlite"):
        return create_engine(url, **engine_options)

    sqlite_engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        **engine_options,
    )

    @event.listens_for(sqlite_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return sqlite_engine


engine = create_database_engine(database_url)

SessionLocal= sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)

Base= declarative_base()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()
