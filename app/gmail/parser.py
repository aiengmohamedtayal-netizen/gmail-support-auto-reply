"""
تحليل رسائل Gmail - استخراج الترويسات والجسم وتنظيف الاقتباسات والتوقيعات.
"""

from __future__ import annotations

import base64
import re
import logging
from datetime import datetime, timezone
from typing import Any
from html import unescape

logger = logging.getLogger(__name__)


# ──────────────── أنماط التنظيف ────────────────

# أنماط إزالة الاقتباسات والتوقيعات
_QUOTE_PATTERNS = [
    re.compile(r"^>.*$", re.MULTILINE),
    re.compile(r"^On .+ wrote:$", re.MULTILINE),
    re.compile(r"^في .+ كتب:$", re.MULTILINE),
    re.compile(r"-{2,}\s*(?:Original Message|Forwarded message).*", re.DOTALL | re.IGNORECASE),
    re.compile(r"-{2,}\s*(?:الرسالة الأصلية).*", re.DOTALL),
]

_SIGNATURE_PATTERNS = [
    re.compile(r"^--\s*$.*", re.MULTILINE | re.DOTALL),
    re.compile(r"^Sent from my .*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^أُرسلت من .*$", re.MULTILINE),
    re.compile(r"^هذه رسالة تلقائية\..*$", re.MULTILINE | re.DOTALL),
]

# نمط إزالة HTML tags
_HTML_TAG = re.compile(r"<[^>]+>")

# نمط تنظيف المسافات المتعددة
_MULTI_SPACE = re.compile(r"\n{3,}")


def _strip_html(html: str) -> str:
    """تحويل HTML إلى نص عادي بسيط."""
    text = _HTML_TAG.sub("", html)
    text = unescape(text)
    return text


def extract_headers(payload: dict[str, Any]) -> dict[str, str]:
    """
    استخراج الترويسات المهمة من payload الرسالة.
    يُرجع قاموسًا بأسماء الترويسات (بأحرف صغيرة) وقيمها.
    """
    headers: dict[str, str] = {}
    important_keys = {
        "from", "to", "subject", "message-id", "in-reply-to",
        "references", "date", "reply-to", "auto-submitted",
        "x-auto-response-suppress", "precedence", "list-unsubscribe",
        "x-mailer",
    }

    for h in payload.get("headers", []):
        name = h.get("name", "").lower()
        if name in important_keys:
            headers[name] = h.get("value", "")

    return headers


def _decode_part(part: dict[str, Any]) -> str:
    """فك تشفير جزء واحد من الرسالة."""
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    try:
        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return decoded
    except Exception:
        logger.warning("فشل في فك تشفير جزء الرسالة")
        return ""


def extract_body(payload: dict[str, Any]) -> str:
    """
    استخراج النص الأساسي من الرسالة.
    يُفضّل text/plain على text/html.
    """
    mime_type = payload.get("mimeType", "")

    # رسالة بسيطة بدون أجزاء
    if mime_type == "text/plain":
        return _decode_part(payload)
    if mime_type == "text/html":
        return _strip_html(_decode_part(payload))

    # رسالة متعددة الأجزاء
    parts = payload.get("parts", [])
    plain_text = ""
    html_text = ""

    for part in parts:
        part_mime = part.get("mimeType", "")
        if part_mime == "text/plain":
            plain_text += _decode_part(part)
        elif part_mime == "text/html":
            html_text += _decode_part(part)
        elif "parts" in part:
            # أجزاء متداخلة (multipart/alternative داخل multipart/mixed)
            for sub in part.get("parts", []):
                sub_mime = sub.get("mimeType", "")
                if sub_mime == "text/plain":
                    plain_text += _decode_part(sub)
                elif sub_mime == "text/html":
                    html_text += _decode_part(sub)

    if plain_text:
        return plain_text
    if html_text:
        return _strip_html(html_text)

    return ""


def clean_body(raw_body: str) -> str:
    """
    تنظيف جسم الرسالة من الاقتباسات والتوقيعات والمسافات الزائدة.
    """
    text = raw_body

    # إزالة التوقيعات أولاً (لأنها عادة في نهاية الرسالة)
    for pat in _SIGNATURE_PATTERNS:
        text = pat.sub("", text)

    # إزالة الاقتباسات
    for pat in _QUOTE_PATTERNS:
        text = pat.sub("", text)

    # تنظيف المسافات
    text = _MULTI_SPACE.sub("\n\n", text)
    text = text.strip()

    return text


def extract_sender_email(from_header: str) -> str:
    """
    استخراج عنوان البريد من ترويسة From.
    مثال: 'أحمد <ahmed@example.com>' → 'ahmed@example.com'
    """
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    # إذا كان العنوان بدون أقواس
    return from_header.strip().lower()


def parse_internal_date(msg: dict[str, Any]) -> datetime | None:
    """
    تحويل internalDate (بالميلي ثانية) إلى كائن datetime.
    """
    raw = msg.get("internalDate")
    if raw:
        try:
            return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
        except (ValueError, TypeError):
            pass
    return None


def parse_message(msg: dict[str, Any]) -> dict[str, Any]:
    """
    تحليل رسالة Gmail كاملة وإرجاع بيانات منظمة.
    """
    payload = msg.get("payload", {})
    headers = extract_headers(payload)
    raw_body = extract_body(payload)
    cleaned = clean_body(raw_body)
    sender = extract_sender_email(headers.get("from", ""))

    return {
        "message_id": msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "gmail_message_id_header": headers.get("message-id", ""),
        "subject": headers.get("subject", "(بدون موضوع)"),
        "from": headers.get("from", ""),
        "sender_email": sender,
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "in_reply_to": headers.get("in-reply-to", ""),
        "references": headers.get("references", ""),
        "auto_submitted": headers.get("auto-submitted", ""),
        "precedence": headers.get("precedence", ""),
        "list_unsubscribe": headers.get("list-unsubscribe", ""),
        "x_auto_response_suppress": headers.get("x-auto-response-suppress", ""),
        "raw_headers": headers,
        "body_raw": raw_body,
        "body_clean": cleaned,
        "internal_date": parse_internal_date(msg),
        "label_ids": msg.get("labelIds", []),
    }
