"""
حواجز الأمان ومنع الحلقات - قواعد لتحديد الرسائل التي يجب تجاهلها.
تمنع الرد على الرسائل التلقائية والرسائل المكررة ورسائل no-reply.
"""

from __future__ import annotations

import re
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MessageLog, Ticket, MessageDirection

logger = logging.getLogger(__name__)

# ──────────────── أنماط البريد التلقائي ────────────────

# عناوين no-reply الشائعة
_NOREPLY_PATTERNS = [
    re.compile(r"no[-_.]?reply", re.IGNORECASE),
    re.compile(r"do[-_.]?not[-_.]?reply", re.IGNORECASE),
    re.compile(r"noreply", re.IGNORECASE),
    re.compile(r"mailer[-_.]?daemon", re.IGNORECASE),
    re.compile(r"postmaster", re.IGNORECASE),
]


def is_noreply_address(email: str) -> bool:
    """التحقق مما إذا كان العنوان من نوع no-reply."""
    for pat in _NOREPLY_PATTERNS:
        if pat.search(email):
            return True
    return False


def is_auto_generated(parsed_msg: dict) -> bool:
    """
    التحقق مما إذا كانت الرسالة مولّدة تلقائيًا بناءً على الترويسات.
    تفحص ترويسات Auto-Submitted, Precedence, X-Auto-Response-Suppress.
    """
    # Auto-Submitted: أي قيمة غير "no" تعني رسالة تلقائية
    auto_submitted = parsed_msg.get("auto_submitted", "").lower()
    if auto_submitted and auto_submitted != "no":
        logger.debug("الرسالة تلقائية: Auto-Submitted=%s", auto_submitted)
        return True

    # Precedence: bulk أو list أو junk
    precedence = parsed_msg.get("precedence", "").lower()
    if precedence in ("bulk", "list", "junk"):
        logger.debug("الرسالة تلقائية: Precedence=%s", precedence)
        return True

    # X-Auto-Response-Suppress
    xars = parsed_msg.get("x_auto_response_suppress", "").lower()
    if xars and xars != "none":
        logger.debug("الرسالة تلقائية: X-Auto-Response-Suppress=%s", xars)
        return True

    # List-Unsubscribe يعني قائمة بريدية
    if parsed_msg.get("list_unsubscribe", ""):
        logger.debug("الرسالة من قائمة بريدية (List-Unsubscribe موجود)")
        return True

    return False


def is_own_reply(parsed_msg: dict, gmail_user_email: str = "") -> bool:
    """
    التحقق مما إذا كانت الرسالة مرسلة منّا (لمنع الحلقات).
    """
    sender = parsed_msg.get("sender_email", "")
    if gmail_user_email and sender == gmail_user_email.lower():
        return True
    # فحص التوقيع التلقائي
    body = parsed_msg.get("body_clean", "")
    if "هذه رسالة تلقائية" in body:
        return True
    return False


def is_domain_allowed(email: str) -> bool:
    """
    التحقق من قوائم النطاقات المسموح بها والمحظورة.
    إذا كانت قائمة المسموح فارغة، يُسمح لجميع النطاقات ما عدا المحظورة.
    """
    settings = get_settings()
    domain = email.split("@")[-1].lower() if "@" in email else ""

    if not domain:
        return False

    # فحص القائمة المحظورة
    if domain in settings.denied_domains_set:
        logger.info("النطاق محظور: %s", domain)
        return False

    # فحص القائمة المسموحة (إذا كانت فارغة، الكل مسموح)
    allowed = settings.allowed_domains_set
    if allowed and domain not in allowed:
        logger.info("النطاق غير مسموح: %s", domain)
        return False

    return True


def was_already_processed(message_id: str, db: Session) -> bool:
    """
    التحقق مما إذا كانت الرسالة قد تمت معالجتها مسبقًا.
    """
    exists = (
        db.query(MessageLog.id)
        .filter(MessageLog.message_id == message_id)
        .first()
    )
    return exists is not None


def was_replied_in_thread_recently(
    thread_id: str,
    db: Session,
    hours: int = 24,
) -> bool:
    """
    التحقق مما إذا تم الرد على هذه السلسلة خلال آخر N ساعة.
    يمنع إرسال أكثر من رد واحد لنفس السلسلة في اليوم.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent_reply = (
        db.query(MessageLog.id)
        .join(Ticket, Ticket.id == MessageLog.ticket_id)
        .filter(
            Ticket.thread_id == thread_id,
            MessageLog.direction == MessageDirection.OUT,
            MessageLog.internal_date >= cutoff,
        )
        .first()
    )
    return recent_reply is not None


def check_rate_limit(db: Session) -> bool:
    """
    التحقق من عدم تجاوز حد الردود في الساعة.
    يُرجع True إذا كان مسموحًا بالإرسال.
    """
    settings = get_settings()
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    count = (
        db.query(MessageLog.id)
        .filter(
            MessageLog.direction == MessageDirection.OUT,
            MessageLog.internal_date >= one_hour_ago,
        )
        .count()
    )
    if count >= settings.max_replies_per_hour:
        logger.warning(
            "تم الوصول لحد الردود: %d/%d في الساعة",
            count,
            settings.max_replies_per_hour,
        )
        return False
    return True


def should_skip_message(
    parsed_msg: dict,
    db: Session,
    gmail_user_email: str = "",
) -> tuple[bool, str]:
    """
    الفحص الشامل: هل يجب تخطي هذه الرسالة؟
    يُرجع (True, السبب) إذا يجب التخطي، أو (False, "") إذا آمنة للمعالجة.
    """
    sender = parsed_msg.get("sender_email", "")
    message_id = parsed_msg.get("message_id", "")
    thread_id = parsed_msg.get("thread_id", "")

    # 1. عنوان no-reply
    if is_noreply_address(sender):
        return True, f"عنوان no-reply: {sender}"

    # 2. رسالة تلقائية
    if is_auto_generated(parsed_msg):
        return True, "رسالة مولّدة تلقائيًا"

    # 3. رسالة منّا (حلقة)
    if is_own_reply(parsed_msg, gmail_user_email):
        return True, "رسالة مرسلة منّا"

    # 4. نطاق محظور أو غير مسموح
    if not is_domain_allowed(sender):
        return True, f"النطاق غير مسموح: {sender}"

    # 5. تمت معالجتها مسبقًا
    if was_already_processed(message_id, db):
        return True, f"الرسالة معالجة مسبقًا: {message_id}"

    # 6. تم الرد على السلسلة مؤخرًا
    if was_replied_in_thread_recently(thread_id, db):
        return True, f"تم الرد على السلسلة مؤخرًا: {thread_id}"

    # 7. حد المعدل
    if not check_rate_limit(db):
        return True, "تم الوصول لحد الردود في الساعة"

    return False, ""
