"""
اختبارات محرك الحل التلقائي.
"""

import pytest
from app.autosolve.engine import (
    attempt_autosolve,
    generate_ack_reply,
)
from app.rules.classifier import ClassificationResult
from app.models import TicketIntent, TicketPriority, TicketStatus


class TestAutosolveEngine:
    """اختبارات محرك الحل التلقائي."""

    def test_ack_reply_contains_ticket_id(self):
        """فحص أن رسالة التأكيد تحتوي على رقم التذكرة."""
        reply = generate_ack_reply("abc12345-xyz")
        assert "abc12345" in reply
        assert "هذه رسالة تلقائية" in reply

    def test_tracking_with_order_id_solved(self):
        """فحص حل تتبع الشحنة مع رقم الطلب."""
        classification = ClassificationResult(
            intent=TicketIntent.TRACKING_UPDATE,
            priority=TicketPriority.P2,
            order_id="123456",
        )
        result = attempt_autosolve(classification, "ticket-123", "أين شحنتي؟")
        assert result.success is True
        assert result.new_status == TicketStatus.SOLVED
        assert "123456" in result.reply_body

    def test_tracking_without_order_id_needinfo(self):
        """فحص طلب معلومات عند غياب رقم الطلب."""
        classification = ClassificationResult(
            intent=TicketIntent.TRACKING_UPDATE,
            priority=TicketPriority.P2,
            order_id=None,
        )
        result = attempt_autosolve(classification, "ticket-123", "أين شحنتي؟")
        assert result.success is False
        assert result.new_status == TicketStatus.NEED_INFO
        assert "رقم الطلب" in result.reply_body

    def test_invoice_with_invoice_id_solved(self):
        """فحص حل إعادة إرسال الفاتورة مع رقم الفاتورة."""
        classification = ClassificationResult(
            intent=TicketIntent.INVOICE_RESEND,
            priority=TicketPriority.P2,
            invoice_id="789012",
        )
        result = attempt_autosolve(classification, "ticket-456", "أريد الفاتورة")
        assert result.success is True
        assert result.new_status == TicketStatus.SOLVED
        assert "789012" in result.reply_body

    def test_invoice_without_invoice_id_needinfo(self):
        """فحص طلب معلومات عند غياب رقم الفاتورة."""
        classification = ClassificationResult(
            intent=TicketIntent.INVOICE_RESEND,
            priority=TicketPriority.P2,
            invoice_id=None,
        )
        result = attempt_autosolve(classification, "ticket-456", "أريد الفاتورة")
        assert result.success is False
        assert result.new_status == TicketStatus.NEED_INFO
        assert "رقم الفاتورة" in result.reply_body

    def test_general_intent_escalated(self):
        """فحص تصعيد النوايا العامة."""
        classification = ClassificationResult(
            intent=TicketIntent.GENERAL,
            priority=TicketPriority.P3,
        )
        result = attempt_autosolve(classification, "ticket-789", "استفسار عام")
        assert result.success is False
        assert result.new_status == TicketStatus.ESCALATED
