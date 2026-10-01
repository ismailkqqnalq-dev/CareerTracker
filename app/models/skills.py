from app.database.session import Base
from sqlalchemy import Column, Integer, String , ForeignKey

class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String)

class SkillAliases(Base):
    __tablename__ = "skill_aliases"
    id = Column(Integer, primary_key= True, index= True)
    alias = Column(String, unique = True, nullable = False)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), nullable= False)
    