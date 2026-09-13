from app.database.session import Base
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime

class Contact(Base):
    __tablename__="contacts"
    id=Column(Integer, primary_key=True, index=True)
    name=Column(String)
    role=Column(String)
    email=Column(String)
    linkedin=Column(String)
    opportunity_id=Column(Integer, ForeignKey("opportunities.id"))
                 
                 
                 
                 
                 
                 