from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import os
load_dotenv()

database_url = os.getenv("DATABASE_URL", "sqlite:///careertracker.db")
engine= create_engine(
    database_url,
    connect_args={"check_same_thread":False}
    )

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