"""
اختبارات وحدة الحواجز - تتحقق من قواعد تخطي الرسائل.
"""

import pytest
from app.rules.guardrails import (
    is_noreply_address,
    is_auto_generated,
    is_domain_allowed,
)


class TestGuardrails:
    """اختبارات حواجز الأمان."""

    def test_noreply_detection(self):
        """فحص اكتشاف عناوين no-reply."""
        assert is_noreply_address("noreply@example.com") is True
        assert is_noreply_address("no-reply@company.org") is True
        assert is_noreply_address("do_not_reply@test.com") is True
        assert is_noreply_address("mailer-daemon@gmail.com") is True
        assert is_noreply_address("support@company.com") is False
        assert is_noreply_address("ahmed@example.com") is False

    def test_auto_generated_detection(self):
        """فحص اكتشاف الرسائل التلقائية."""
        # رسالة تلقائية
        msg1 = {"auto_submitted": "auto-replied"}
        assert is_auto_generated(msg1) is True

        # رسالة قائمة بريدية
        msg2 = {"precedence": "bulk"}
        assert is_auto_generated(msg2) is True

        # رسالة عادية
        msg3 = {"auto_submitted": "no"}
        assert is_auto_generated(msg3) is False

        # رسالة بدون ترويسات
        msg4 = {}
        assert is_auto_generated(msg4) is False

    def test_domain_allowed_default(self):
        """فحص السماح الافتراضي لجميع النطاقات."""
        # بدون إعدادات، يُسمح لجميع النطاقات
        # (هذا يعتمد على إعدادات الـ config الافتراضية)
        assert is_domain_allowed("user@example.com") is True
        assert is_domain_allowed("test@gmail.com") is True
