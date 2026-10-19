from app.database.session import Base
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)

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

class UserSkill(Base):
    __tablename__ = "user_skills"

    __table_args__ = (
        UniqueConstraint("user_id", "skill_id", name="uq_user_skills_user_skill"),
        CheckConstraint(
            "proficiency_level IN ('beginner', 'intermediate', 'advanced', 'expert')",
            name="ck_user_skills_proficiency_level",
        ),
        CheckConstraint(
            "years_experience >= 0",
            name="ck_user_skills_years_experience_non_negative",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id = Column(
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proficiency_level = Column(String(20), nullable=False, default="beginner")
    years_experience = Column(Float, nullable=False, default=0.0)


class SkillSuggestion(Base):
    __tablename__ = "skill_suggestions"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "normalized_name",
            name="uq_skill_suggestions_user_normalized_name",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_skill_suggestions_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_name = Column(String(120), nullable=False)
    normalized_name = Column(String(120), nullable=False)
    resolved_skill_id = Column(
        Integer,
        ForeignKey("skills.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
