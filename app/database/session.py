from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

database_url="sqlite:///careertracker.db"
engine= create_engine(
    database_url,
    connect_args={"check_same_thread":False}
    )

SessionLocal= sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)