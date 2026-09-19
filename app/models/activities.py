from app.database.session import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

class Activity(Base):
    __tablename__= "activities"
    
    id =Column(Integer, primary_key=True, index=True)
    opportunity_id= Column(Integer, ForeignKey("opportunities.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    activity_type = Column(String)
    dates = Column(DateTime)
    notes = Column(String)