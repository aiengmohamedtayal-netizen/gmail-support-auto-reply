"""
اختبارات محلل الرسائل.
"""

import pytest
from app.gmail.parser import (
    extract_sender_email,
    clean_body,
    _strip_html,
)


class TestParser:
    """اختبارات محلل الرسائل."""

    def test_extract_sender_email_with_brackets(self):
        """فحص استخراج البريد من ترويسة مع أقواس."""
        result = extract_sender_email("أحمد محمد <ahmed@example.com>")
        assert result == "ahmed@example.com"

    def test_extract_sender_email_plain(self):
        """فحص استخراج البريد العادي."""
        result = extract_sender_email("ahmed@example.com")
        assert result == "ahmed@example.com"

    def test_extract_sender_email_uppercase(self):
        """فحص تحويل البريد إلى أحرف صغيرة."""
        result = extract_sender_email("Ahmed@EXAMPLE.COM")
        assert result == "ahmed@example.com"

    def test_clean_body_removes_quotes(self):
        """فحص إزالة الاقتباسات."""
        body = """هذه رسالتي
> هذا اقتباس قديم
> واقتباس آخر
"""
        result = clean_body(body)
        assert ">" not in result
        assert "هذه رسالتي" in result

    def test_clean_body_removes_signature(self):
        """فحص إزالة التوقيع."""
        body = """مرحباً

أريد المساعدة

--
أحمد محمد
الشركة العربية
"""
        result = clean_body(body)
        assert "أريد المساعدة" in result
        # التوقيع بعد -- يُزال
        assert "الشركة العربية" not in result

    def test_strip_html(self):
        """فحص إزالة وسوم HTML."""
        html = "<p>مرحباً <b>بالعالم</b></p>"
        result = _strip_html(html)
        assert "<" not in result
        assert "مرحباً" in result
        assert "بالعالم" in result
