"""
إعدادات التطبيق - تحميل المتغيرات البيئية والتحقق منها.
يتم تحميل القيم من ملف .env أو من متغيرات البيئة مباشرة.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """نموذج الإعدادات الرئيسي - يقرأ من البيئة أو من ملف .env."""

    # ── بيانات اعتماد Gmail ──
    google_client_id: str = Field(default="", description="معرّف عميل Google OAuth")
    google_client_secret: str = Field(default="", description="سر عميل Google OAuth")
    credentials_json_path: str = Field(
        default="credentials.json",
        description="مسار ملف credentials.json من Google Cloud",
    )
    token_json_path: str = Field(
        default="token.json",
        description="مسار ملف token.json للوصول المخزّن",
    )
    gmail_user: str = Field(default="me", description="مستخدم Gmail الهدف")

    # ── قاعدة البيانات ──
    database_url: str = Field(
        default="sqlite:///./complaints.db",
        description="رابط الاتصال بقاعدة البيانات (PostgreSQL أو SQLite)",
    )

    # ── الاستطلاع ──
    poll_interval_seconds: int = Field(
        default=300, ge=30, description="الفاصل الزمني بين عمليات الاستطلاع بالثواني"
    )

    # ── التسميات ──
    auto_replied_label: str = Field(
        default="AUTO_REPLIED",
        description="اسم التسمية التي تُضاف بعد الرد التلقائي",
    )

    # ── حدود المعدل ──
    max_replies_per_hour: int = Field(
        default=50, ge=1, description="الحد الأقصى للردود في الساعة الواحدة"
    )

    # ── قوائم النطاقات ──
    allowed_domains: str = Field(
        default="",
        description="قائمة النطاقات المسموح بها (مفصولة بفاصلة)، فارغ = الكل",
    )
    denied_domains: str = Field(
        default="",
        description="قائمة النطاقات المحظورة (مفصولة بفاصلة)",
    )

    # ── السجلات ──
    log_level: str = Field(default="INFO", description="مستوى تسجيل الأحداث")

    # ── Redis (اختياري) ──
    redis_url: str = Field(default="", description="رابط Redis للاستخدام المستقبلي")

    # ── مساعدات ──
    @property
    def allowed_domains_set(self) -> set[str]:
        """إرجاع مجموعة النطاقات المسموح بها."""
        if not self.allowed_domains.strip():
            return set()
        return {d.strip().lower() for d in self.allowed_domains.split(",") if d.strip()}

    @property
    def denied_domains_set(self) -> set[str]:
        """إرجاع مجموعة النطاقات المحظورة."""
        if not self.denied_domains.strip():
            return set()
        return {d.strip().lower() for d in self.denied_domains.split(",") if d.strip()}

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """إرجاع نسخة وحيدة من الإعدادات (مع تخزين مؤقت)."""
    return Settings()
