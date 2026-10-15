"""
اختبارات وحدة المصنّف - تتحقق من صحة التصنيف والاستخراج.
"""

import pytest
from app.rules.classifier import (
    classify,
    ClassificationResult,
    TicketIntent,
    TicketPriority,
)


class TestClassifier:
    """اختبارات مصنّف النوايا."""

    def test_tracking_intent_arabic(self):
        """فحص تصنيف رسالة تتبع بالعربية."""
        result = classify("أين شحنتي؟", "أريد معرفة حالة الشحن")
        assert result.intent == TicketIntent.TRACKING_UPDATE
        assert result.priority == TicketPriority.P2

    def test_tracking_intent_english(self):
        """فحص تصنيف رسالة تتبع بالإنجليزية."""
        result = classify("Where is my package?", "I need tracking update")
        assert result.intent == TicketIntent.TRACKING_UPDATE

    def test_invoice_intent_arabic(self):
        """فحص تصنيف رسالة فاتورة بالعربية."""
        result = classify("فاتورة", "أحتاج نسخة من الفاتورة")
        assert result.intent == TicketIntent.INVOICE_RESEND

    def test_invoice_intent_english(self):
        """فحص تصنيف رسالة فاتورة بالإنجليزية."""
        result = classify("Invoice request", "Please resend the invoice")
        assert result.intent == TicketIntent.INVOICE_RESEND

    def test_general_intent(self):
        """فحص تصنيف رسالة عامة."""
        result = classify("مرحبا", "ما هي ساعات العمل؟")
        assert result.intent == TicketIntent.GENERAL
        assert result.priority == TicketPriority.P3

    def test_urgent_priority(self):
        """فحص اكتشاف الأولوية العاجلة."""
        result = classify("عاجل جداً", "هذا احتيال!")
        assert result.priority == TicketPriority.P1

    def test_order_id_extraction(self):
        """فحص استخراج رقم الطلب."""
        result = classify("تتبع", "أريد تتبع طلب #123456")
        assert result.order_id == "123456"

    def test_order_id_extraction_arabic(self):
        """فحص استخراج رقم الطلب بالعربية."""
        result = classify("شحنة", "الطلب رقم 987654 لم يصل")
        assert result.order_id == "987654"

    def test_invoice_id_extraction(self):
        """فحص استخراج رقم الفاتورة."""
        result = classify("فاتورة", "أحتاج فاتورة #456789")
        assert result.invoice_id == "456789"

    def test_no_id_extraction(self):
        """فحص عدم استخراج رقم عند غيابه."""
        result = classify("تتبع", "أين شحنتي؟")
        assert result.order_id is None
        assert result.invoice_id is None
