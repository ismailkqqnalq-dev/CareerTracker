from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.database.session import Base


class RefreshToken(Base):
    """Uzun ömürlü oturum: token'ın kendisi değil, SHA-256 özeti saklanır."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True)
    # Aynı girişten rotasyonla türeyen token'lar bir aile oluşturur; yeniden
    # kullanım (çalınma belirtisi) görülünce ailenin tamamı iptal edilir.
    family_id = Column(String(36), nullable=False, index=True)
    persistent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
