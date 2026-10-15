"""
عميل Gmail - إعداد اتصال OAuth2 وبناء خدمة Gmail API.
يدعم تخزين الرمز المميز وتحديثه تلقائيًا.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

from app.config import get_settings

logger = logging.getLogger(__name__)

# نطاقات الصلاحيات المطلوبة من Gmail API
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.labels",
]

# متغير عام لتخزين الخدمة (نسخة واحدة)
_service: Optional[Resource] = None


def _load_or_create_credentials(settings) -> Credentials:
    """
    تحميل بيانات الاعتماد من ملف token.json إذا وُجد،
    وإلا بدء تدفق OAuth2 التفاعلي.
    """
    creds: Optional[Credentials] = None
    token_path = Path(settings.token_json_path)
    creds_path = Path(settings.credentials_json_path)

    # محاولة تحميل الرمز المخزّن
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        logger.info("تم تحميل الرمز المميز من %s", token_path)

    # تحديث الرمز إذا انتهت صلاحيته
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("تم تحديث الرمز المميز بنجاح")
        except Exception:
            logger.warning("فشل تحديث الرمز، سيتم إعادة المصادقة")
            creds = None

    # إذا لا يوجد رمز صالح، بدء تدفق المصادقة
    if not creds or not creds.valid:
        if not creds_path.exists():
            raise FileNotFoundError(
                f"ملف بيانات الاعتماد غير موجود: {creds_path}. "
                "يرجى تنزيله من Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        creds = flow.run_local_server(port=0)
        logger.info("تمت المصادقة بنجاح عبر OAuth2")

    # حفظ الرمز للاستخدام لاحقًا
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    logger.info("تم حفظ الرمز المميز في %s", token_path)

    return creds


def get_gmail_service(force_new: bool = False) -> Resource:
    """
    الحصول على خدمة Gmail API جاهزة للاستخدام.
    تُخزّن مؤقتًا بعد أول استدعاء.
    """
    global _service
    if _service is not None and not force_new:
        return _service

    settings = get_settings()
    creds = _load_or_create_credentials(settings)

    _service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    logger.info("تم بناء خدمة Gmail API بنجاح")
    return _service


def ensure_label_exists(label_name: str) -> str:
    """
    التأكد من وجود التسمية وإنشاؤها إذا لم تكن موجودة.
    يُرجع معرّف التسمية.
    """
    service = get_gmail_service()
    settings = get_settings()

    # جلب جميع التسميات الحالية
    results = service.users().labels().list(userId=settings.gmail_user).execute()
    labels = results.get("labels", [])

    for label in labels:
        if label["name"] == label_name:
            logger.info("التسمية '%s' موجودة بالفعل (id=%s)", label_name, label["id"])
            return label["id"]

    # إنشاء التسمية
    body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    created = (
        service.users()
        .labels()
        .create(userId=settings.gmail_user, body=body)
        .execute()
    )
    logger.info("تم إنشاء التسمية '%s' (id=%s)", label_name, created["id"])
    return created["id"]
