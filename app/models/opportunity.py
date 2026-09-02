from app.database.session import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, column

class Opportunity(Base):
    __tablename__="opportunities"
    id=Column(Integer, primary_key=True, index=True)
    company=Column(String)
    position=Column(String)
    type=Column(String)
    application_date=Column(DateTime)
    job_link=Column(String)
    salary=Column(Integer)
    location=Column(String)
    status=Column(String)
    notes=Column(String)
    next_action=Column(String)
    last_contact_date=Column(DateTime)