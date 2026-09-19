from app.database.session import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean

class Task(Base):
     __tablename__ = "tasks"

     id =Column(Integer, primary_key=True, index=True)
     opportunity_id= Column(Integer, ForeignKey("opportunities.id"), nullable=False)
     description = Column(String)
     due_date = Column(DateTime)
     is_completed = Column(Boolean, default=False)