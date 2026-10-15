"""
نماذج قاعدة البيانات - التذاكر وسجل الرسائل.
يُستخدم UUID كمعرّف رئيسي لسهولة التوزيع المستقبلي.
"""

from __future__ import annotations

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db import Base


# ──────────────── تعدادات الحالة والأولوية ────────────────


class TicketStatus(str, enum.Enum):
    """حالات التذكرة الممكنة."""
    NEW = "NEW"
    ACKED = "ACKED"
    NEED_INFO = "NEED_INFO"
    AUTO_PROCESSING = "AUTO_PROCESSING"
    SOLVED = "SOLVED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class TicketIntent(str, enum.Enum):
    """تصنيفات نوايا الشكوى."""
    TRACKING_UPDATE = "tracking_update"
    INVOICE_RESEND = "invoice_resend"
    GENERAL = "general"


class TicketPriority(str, enum.Enum):
    """مستويات الأولوية."""
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class MessageDirection(str, enum.Enum):
    """اتجاه الرسالة: واردة أو صادرة."""
    IN = "IN"
    OUT = "OUT"


# ──────────────── نموذج التذكرة ────────────────


def _uuid() -> str:
    """توليد UUID جديد كنص."""
    return str(uuid.uuid4())


class Ticket(Base):
    """
    جدول التذاكر الرئيسي.
    كل سلسلة بريد (thread) تُمثّل بتذكرة واحدة.
    """
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=_uuid)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    customer_email = Column(String(320), nullable=False, index=True)
    subject = Column(Text, nullable=False)
    thread_id = Column(String(64), nullable=False, unique=True, index=True)

    status = Column(
        Enum(TicketStatus),
        default=TicketStatus.NEW,
        nullable=False,
        index=True,
    )
    intent = Column(
        Enum(TicketIntent),
        default=TicketIntent.GENERAL,
        nullable=False,
        index=True,
    )
    priority = Column(
        Enum(TicketPriority),
        default=TicketPriority.P3,
        nullable=False,
        index=True,
    )

    last_inbound_message_id = Column(String(128), nullable=True)
    last_outbound_message_id = Column(String(128), nullable=True)
    last_replied_at = Column(DateTime(timezone=True), nullable=True)

    confidence = Column(Float, default=1.0, nullable=False)

    # العلاقة مع سجل الرسائل
    messages = relationship(
        "MessageLog",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="MessageLog.internal_date",
    )

    def __repr__(self) -> str:
        return (
            f"<Ticket id={self.id[:8]}… status={self.status.value} "
            f"intent={self.intent.value}>"
        )


# ──────────────── نموذج سجل الرسائل ────────────────


class MessageLog(Base):
    """
    سجل كل رسالة مرتبطة بتذكرة.
    يُستخدم لتتبع الرسائل الواردة والصادرة ومنع التكرار.
    """
    __tablename__ = "message_logs"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(
        String(36),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction = Column(Enum(MessageDirection), nullable=False)
    message_id = Column(String(256), nullable=False, unique=True, index=True)
    internal_date = Column(DateTime(timezone=True), nullable=True)
    raw_headers = Column(JSON, nullable=True)
    body_clean = Column(Text, nullable=True)

    # العلاقة العكسية مع التذكرة
    ticket = relationship("Ticket", back_populates="messages")

    # فهرس مركّب للبحث السريع
    __table_args__ = (
        Index("ix_msglog_ticket_direction", "ticket_id", "direction"),
    )

    def __repr__(self) -> str:
        return (
            f"<MessageLog id={self.id[:8]}… dir={self.direction.value} "
            f"msg_id={self.message_id[:20]}…>"
        )
