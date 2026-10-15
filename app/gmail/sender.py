"""
إرسال الردود عبر Gmail - الرد في نفس السلسلة مع الترويسات الصحيحة.
يدعم وسم الرسائل وإزالة تسمية غير مقروء وإضافة تسمية AUTO_REPLIED.
"""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from typing import Any

from app.config import get_settings
from app.gmail.client import get_gmail_service, ensure_label_exists

logger = logging.getLogger(__name__)


def send_reply(
    thread_id: str,
    to_email: str,
    subject: str,
    body_text: str,
    original_message_id_header: str,
    references: str = "",
) -> dict[str, Any] | None:
    """
    إرسال رد في نفس سلسلة البريد.
    يضبط الترويسات In-Reply-To و References و Subject بشكل صحيح.
    يُرجع استجابة Gmail API أو None عند الفشل.
    """
    settings = get_settings()
    service = get_gmail_service()

    # بناء رسالة MIME
    msg = MIMEText(body_text, "plain", "utf-8")
    msg["To"] = to_email
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    # ترويسات الربط بالسلسلة
    if original_message_id_header:
        msg["In-Reply-To"] = original_message_id_header
        # بناء سلسلة References
        if references:
            msg["References"] = f"{references} {original_message_id_header}"
        else:
            msg["References"] = original_message_id_header

    # تشفير الرسالة
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    body = {
        "raw": raw,
        "threadId": thread_id,
    }

    try:
        sent = (
            service.users()
            .messages()
            .send(userId=settings.gmail_user, body=body)
            .execute()
        )
        logger.info(
            "تم إرسال الرد بنجاح",
            extra={
                "thread_id": thread_id,
                "sent_message_id": sent.get("id"),
                "to": to_email,
            },
        )
        return sent
    except Exception:
        logger.exception(
            "فشل في إرسال الرد",
            extra={"thread_id": thread_id, "to": to_email},
        )
        return None


def mark_as_read_and_label(message_id: str) -> bool:
    """
    إزالة تسمية UNREAD وإضافة تسمية AUTO_REPLIED.
    يُرجع True عند النجاح.
    """
    settings = get_settings()
    service = get_gmail_service()

    try:
        # التأكد من وجود التسمية
        label_id = ensure_label_exists(settings.auto_replied_label)

        service.users().messages().modify(
            userId=settings.gmail_user,
            id=message_id,
            body={
                "removeLabelIds": ["UNREAD"],
                "addLabelIds": [label_id],
            },
        ).execute()

        logger.info(
            "تم تحديث تسميات الرسالة",
            extra={"message_id": message_id, "label": settings.auto_replied_label},
        )
        return True
    except Exception:
        logger.exception(
            "فشل في تحديث تسميات الرسالة",
            extra={"message_id": message_id},
        )
        return False
