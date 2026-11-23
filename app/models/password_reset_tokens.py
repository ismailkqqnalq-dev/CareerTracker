from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.database.session import Base


class PasswordResetToken(Base):
    """Tek kullanımlık şifre sıfırlama bağlantısı: token'ın yalnızca SHA-256 özeti saklanır."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
