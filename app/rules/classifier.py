"""
مصنّف النوايا والأولويات - يعتمد على الكلمات المفتاحية (بدون ذكاء اصطناعي في MVP).
يستخرج أيضًا المعرّفات المهمة مثل رقم الطلب ورقم الفاتورة.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

from app.models import TicketIntent, TicketPriority

logger = logging.getLogger(__name__)


# ──────────────── الكلمات المفتاحية حسب النية ────────────────

TRACKING_KEYWORDS = [
    "tracking", "shipment", "شحن", "تأخير", "وصل", "delivery",
    "توصيل", "شحنة", "تتبع", "طرد", "track",
]

INVOICE_KEYWORDS = [
    "invoice", "فاتورة", "bill", "receipt", "ايصال",
    "إيصال", "فواتير", "حساب",
]

# كلمات الأولوية العالية (P1)
URGENT_KEYWORDS = [
    "urgent", "عاجل", "تهديد", "قانون", "fraud", "احتيال",
    "محامي", "شرطة", "نصب", "سرقة", "خطير", "فوري",
    "emergency", "critical", "asap",
]

# ──────────────── أنماط استخراج المعرّفات ────────────────

# رقم الطلب: order#12345 أو طلب رقم 12345
ORDER_ID_PATTERN = re.compile(
    r"(?:order|طلب|الطلب)\s*#?\s*(\d{5,})",
    re.IGNORECASE,
)

# رقم الفاتورة: invoice#12345 أو فاتورة رقم 12345
INVOICE_ID_PATTERN = re.compile(
    r"(?:invoice|فاتورة|الفاتورة)\s*#?\s*(\d{5,})",
    re.IGNORECASE,
)


@dataclass
class ClassificationResult:
    """نتيجة التصنيف مع البيانات المستخرجة."""

    intent: TicketIntent = TicketIntent.GENERAL
    priority: TicketPriority = TicketPriority.P3
    confidence: float = 1.0
    order_id: str | None = None
    invoice_id: str | None = None
    matched_keywords: list[str] = field(default_factory=list)


def _text_contains_any(text: str, keywords: list[str]) -> list[str]:
    """البحث عن الكلمات المفتاحية في النص (غير حساس لحالة الأحرف)."""
    text_lower = text.lower()
    found = []
    for kw in keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def _extract_ids(text: str) -> dict[str, str | None]:
    """استخراج رقم الطلب ورقم الفاتورة من النص."""
    ids: dict[str, str | None] = {"order_id": None, "invoice_id": None}

    order_match = ORDER_ID_PATTERN.search(text)
    if order_match:
        ids["order_id"] = order_match.group(1)

    invoice_match = INVOICE_ID_PATTERN.search(text)
    if invoice_match:
        ids["invoice_id"] = invoice_match.group(1)

    return ids


def classify(subject: str, body: str) -> ClassificationResult:
    """
    تصنيف الرسالة بناءً على الموضوع والجسم.
    الأولوية: tracking_update > invoice_resend > general.
    الأولوية العاجلة تُطبّق بشكل مستقل عن النية.
    """
    combined = f"{subject} {body}"
    result = ClassificationResult()

    # ── استخراج المعرّفات ──
    ids = _extract_ids(combined)
    result.order_id = ids["order_id"]
    result.invoice_id = ids["invoice_id"]

    # ── فحص الأولوية (مستقل عن النية) ──
    urgent_hits = _text_contains_any(combined, URGENT_KEYWORDS)
    if urgent_hits:
        result.priority = TicketPriority.P1
        result.matched_keywords.extend(urgent_hits)
        logger.info("تم اكتشاف أولوية عاجلة: %s", urgent_hits)

    # ── تصنيف النية ──
    tracking_hits = _text_contains_any(combined, TRACKING_KEYWORDS)
    invoice_hits = _text_contains_any(combined, INVOICE_KEYWORDS)

    if tracking_hits:
        result.intent = TicketIntent.TRACKING_UPDATE
        result.matched_keywords.extend(tracking_hits)
        # إذا لم تكن عاجلة، التتبع عادة P2
        if result.priority != TicketPriority.P1:
            result.priority = TicketPriority.P2
        logger.info(
            "تصنيف: tracking_update (كلمات: %s، order_id: %s)",
            tracking_hits,
            result.order_id,
        )
    elif invoice_hits:
        result.intent = TicketIntent.INVOICE_RESEND
        result.matched_keywords.extend(invoice_hits)
        if result.priority != TicketPriority.P1:
            result.priority = TicketPriority.P2
        logger.info(
            "تصنيف: invoice_resend (كلمات: %s، invoice_id: %s)",
            invoice_hits,
            result.invoice_id,
        )
    else:
        result.intent = TicketIntent.GENERAL
        logger.info("تصنيف: general (لا توجد كلمات مفتاحية مطابقة)")

    return result
