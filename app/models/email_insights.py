from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, func

from app.database.session import Base


class InboundAddress(Base):
    """Kullanıcının işe alım e-postalarını yönlendirdiği, tahmin edilemeyen adres."""

    __tablename__ = "inbound_addresses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    local_part = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # Gmail yönlendirme kurulurken bu adrese bir doğrulama kodu gönderir; kullanıcıya gösterilir.
    verification_code = Column(String(32), nullable=True)
    verification_received_at = Column(DateTime(timezone=True), nullable=True)


class EmailSuggestion(Base):
    """Gelen bir e-postadan çıkan, kullanıcının onayını bekleyen güncelleme.

    E-postanın metni saklanmaz; yalnızca gönderen, konu, tür ve önerilen değişiklikler.
    """

    __tablename__ = "email_suggestions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True)
    email_type = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    sender = Column(String(320), nullable=False, default="")
    subject = Column(String(500), nullable=False, default="")
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    suggested_status = Column(String(50), nullable=True)
    suggested_last_contact_date = Column(Date, nullable=True)
    suggested_task_description = Column(String(2000), nullable=True)
    suggested_task_due_date = Column(Date, nullable=True)
    # pending | applied | dismissed
    state = Column(String(16), nullable=False, default="pending", index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
