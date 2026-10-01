from app.database.session import Base
from sqlalchemy import Column, Integer, ForeignKey

class OpportunitySkill(Base):
    __tablename__ = "opportunity_skills"
    opportunity_id = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)