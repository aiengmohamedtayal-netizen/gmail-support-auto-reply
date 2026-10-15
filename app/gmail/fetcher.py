"""
جلب الرسائل من Gmail - قائمة الرسائل غير المقروءة وتفاصيل كل رسالة.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.gmail.client import get_gmail_service

logger = logging.getLogger(__name__)


def list_unread_message_ids(max_results: int = 50) -> list[dict[str, str]]:
    """
    جلب قائمة معرّفات الرسائل غير المقروءة من البريد الوارد.
    يُرجع قائمة من القواميس تحتوي على id و threadId.
    """
    settings = get_settings()
    service = get_gmail_service()

    try:
        response = (
            service.users()
            .messages()
            .list(
                userId=settings.gmail_user,
                q="is:unread in:inbox",
                maxResults=max_results,
            )
            .execute()
        )
    except Exception:
        logger.exception("فشل في جلب قائمة الرسائل غير المقروءة")
        return []

    messages = response.get("messages", [])
    logger.info("تم العثور على %d رسالة غير مقروءة", len(messages))
    return messages


def get_message_detail(message_id: str) -> dict[str, Any] | None:
    """
    جلب التفاصيل الكاملة لرسالة واحدة بما في ذلك الترويسات والجسم.
    يُرجع الاستجابة الكاملة من Gmail API أو None عند الفشل.
    """
    settings = get_settings()
    service = get_gmail_service()

    try:
        msg = (
            service.users()
            .messages()
            .get(
                userId=settings.gmail_user,
                id=message_id,
                format="full",
            )
            .execute()
        )
        return msg
    except Exception:
        logger.exception("فشل في جلب تفاصيل الرسالة %s", message_id)
        return None
