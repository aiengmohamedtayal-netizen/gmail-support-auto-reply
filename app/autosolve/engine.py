"""
محرك الحل التلقائي - ينفذ إجراءات بناءً على تصنيف النية.
يدعم حاليًا: تحديث التتبع وإعادة إرسال الفاتورة.
يحتوي على تكاملات وهمية (dummy) لأغراض MVP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models import TicketIntent, TicketStatus
from app.rules.classifier import ClassificationResult

logger = logging.getLogger(__name__)


# ──────────────── قوالب الردود بالعربية ────────────────

# تذييل مشترك لجميع الردود
FOOTER = "\n\n---\nهذه رسالة تلقائية."

# رسالة تأكيد الاستلام
ACK_TEMPLATE = """مرحبًا،

شكرًا لتواصلك معنا. تم استلام رسالتك وإنشاء تذكرة دعم.

📋 رقم التذكرة: {ticket_id}
⏰ سيتم الرد خلال: 24 ساعة عمل

سنعمل على حل مشكلتك في أقرب وقت ممكن.{footer}"""

# رسالة طلب معلومات إضافية
NEED_INFO_TEMPLATE = """مرحبًا،

شكرًا لتواصلك معنا بخصوص: {subject}

نحتاج إلى المعلومات التالية لمتابعة طلبك:

{missing_fields}

يرجى الرد على هذه الرسالة في نفس السلسلة مع المعلومات المطلوبة.{footer}"""

# رسالة حل تتبع الشحنة
TRACKING_SOLVED_TEMPLATE = """مرحبًا،

تم التحقق من حالة طلبك رقم #{order_id}:

📦 حالة الشحنة: قيد التوصيل
🚚 شركة الشحن: الناقل السريع
📍 آخر موقع: مركز التوزيع الرئيسي
📅 موعد التسليم المتوقع: {eta}

يمكنك تتبع شحنتك عبر الرابط التالي:
🔗 https://tracking.example.com/{order_id}

إذا لم تصلك الشحنة في الموعد المحدد، يرجى الرد على هذه الرسالة.{footer}"""

# رسالة حل إعادة إرسال الفاتورة
INVOICE_SOLVED_TEMPLATE = """مرحبًا،

تم إعادة إرسال الفاتورة رقم #{invoice_id} بنجاح.

📄 يمكنك تحميل الفاتورة من الرابط التالي:
🔗 https://invoices.example.com/download/{invoice_id}

ℹ️ الرابط صالح لمدة 7 أيام.

إذا واجهت أي مشكلة في تحميل الفاتورة، يرجى الرد على هذه الرسالة.{footer}"""

# رسالة التصعيد (للنوايا العامة)
ESCALATED_TEMPLATE = """مرحبًا،

شكرًا لتواصلك معنا. تم استلام رسالتك وتحويلها لفريق الدعم المتخصص.

📋 رقم التذكرة: {ticket_id}
⏰ سيتواصل معك أحد ممثلي الدعم خلال: 4 ساعات عمل

نعتذر عن أي إزعاج ونعمل على خدمتك بأسرع وقت.{footer}"""


# ──────────────── نتيجة الحل التلقائي ────────────────


@dataclass
class AutoSolveResult:
    """نتيجة محاولة الحل التلقائي."""

    success: bool
    new_status: TicketStatus
    reply_body: str
    action_taken: str = ""


# ──────────────── التكاملات الوهمية ────────────────


def _dummy_tracking_lookup(order_id: str) -> dict:
    """
    تكامل وهمي: البحث عن حالة الشحنة.
    في الإنتاج، سيتصل بـ API شركة الشحن.
    """
    eta = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    return {
        "status": "in_transit",
        "carrier": "الناقل السريع",
        "location": "مركز التوزيع الرئيسي",
        "eta": eta,
    }


def _dummy_invoice_resend(invoice_id: str) -> dict:
    """
    تكامل وهمي: إعادة إرسال الفاتورة.
    في الإنتاج، سيتصل بنظام الفواتير.
    """
    return {
        "download_url": f"https://invoices.example.com/download/{invoice_id}",
        "valid_days": 7,
    }


# ──────────────── المحرك الرئيسي ────────────────


def generate_ack_reply(ticket_id: str) -> str:
    """توليد رسالة تأكيد الاستلام."""
    return ACK_TEMPLATE.format(ticket_id=ticket_id[:8], footer=FOOTER)


def attempt_autosolve(
    classification: ClassificationResult,
    ticket_id: str,
    subject: str,
) -> AutoSolveResult:
    """
    محاولة الحل التلقائي بناءً على تصنيف النية.
    يُرجع نتيجة تحتوي على حالة التذكرة الجديدة ونص الرد.
    """
    intent = classification.intent

    # ── تحديث التتبع ──
    if intent == TicketIntent.TRACKING_UPDATE:
        if not classification.order_id:
            # نحتاج رقم الطلب
            missing = "• رقم الطلب (مثال: طلب #12345 أو order #12345)"
            body = NEED_INFO_TEMPLATE.format(
                subject=subject,
                missing_fields=missing,
                footer=FOOTER,
            )
            logger.info("حل تلقائي: NEED_INFO (order_id مفقود)")
            return AutoSolveResult(
                success=False,
                new_status=TicketStatus.NEED_INFO,
                reply_body=body,
                action_taken="طلب رقم الطلب",
            )

        # لدينا رقم الطلب - محاولة الحل
        tracking = _dummy_tracking_lookup(classification.order_id)
        body = TRACKING_SOLVED_TEMPLATE.format(
            order_id=classification.order_id,
            eta=tracking["eta"],
            footer=FOOTER,
        )
        logger.info(
            "حل تلقائي: SOLVED (tracking_update, order_id=%s)",
            classification.order_id,
        )
        return AutoSolveResult(
            success=True,
            new_status=TicketStatus.SOLVED,
            reply_body=body,
            action_taken=f"تم إرسال حالة التتبع للطلب #{classification.order_id}",
        )

    # ── إعادة إرسال الفاتورة ──
    if intent == TicketIntent.INVOICE_RESEND:
        if not classification.invoice_id:
            # نحتاج رقم الفاتورة
            missing = "• رقم الفاتورة (مثال: فاتورة #12345 أو invoice #12345)"
            body = NEED_INFO_TEMPLATE.format(
                subject=subject,
                missing_fields=missing,
                footer=FOOTER,
            )
            logger.info("حل تلقائي: NEED_INFO (invoice_id مفقود)")
            return AutoSolveResult(
                success=False,
                new_status=TicketStatus.NEED_INFO,
                reply_body=body,
                action_taken="طلب رقم الفاتورة",
            )

        # لدينا رقم الفاتورة - محاولة الحل
        _dummy_invoice_resend(classification.invoice_id)
        body = INVOICE_SOLVED_TEMPLATE.format(
            invoice_id=classification.invoice_id,
            footer=FOOTER,
        )
        logger.info(
            "حل تلقائي: SOLVED (invoice_resend, invoice_id=%s)",
            classification.invoice_id,
        )
        return AutoSolveResult(
            success=True,
            new_status=TicketStatus.SOLVED,
            reply_body=body,
            action_taken=f"تم إعادة إرسال الفاتورة #{classification.invoice_id}",
        )

    # ── عام: تأكيد + تصعيد ──
    body = ESCALATED_TEMPLATE.format(
        ticket_id=ticket_id[:8],
        footer=FOOTER,
    )
    logger.info("حل تلقائي: ESCALATED (نية عامة)")
    return AutoSolveResult(
        success=False,
        new_status=TicketStatus.ESCALATED,
        reply_body=body,
        action_taken="تصعيد لفريق الدعم",
    )
