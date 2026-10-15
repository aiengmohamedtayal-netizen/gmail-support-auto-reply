"""
إعداد نظام السجلات المهيكلة بتنسيق JSON.
يُستخدم في جميع أنحاء التطبيق لتسجيل الأحداث بشكل منظم.
"""

from __future__ import annotations

import logging
import json
import sys
from datetime import datetime, timezone

from app.config import get_settings


class JSONFormatter(logging.Formatter):
    """
    منسّق سجلات بتنسيق JSON.
    يُخرج كل سجل كسطر JSON واحد مع بيانات وصفية.
    """

    # الحقول الحساسة التي يجب تنقيحها
    SENSITIVE_KEYS = {
        "password", "secret", "token", "api_key", "authorization",
        "cvv", "otp", "credit_card", "ssn",
    }

    def _redact(self, data: dict) -> dict:
        """تنقيح البيانات الحساسة من السجلات."""
        redacted = {}
        for key, value in data.items():
            if any(s in key.lower() for s in self.SENSITIVE_KEYS):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact(value)
            else:
                redacted[key] = value
        return redacted

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # إضافة البيانات الإضافية (extra)
        # جمع المفاتيح الإضافية التي لا تنتمي للسجل الأساسي
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated",
            "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "filename", "module", "pathname", "levelname", "levelno",
            "process", "processName", "thread", "threadName",
            "msecs", "message", "taskName",
        }
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs
        }
        if extras:
            log_entry["extra"] = self._redact(extras)

        # إضافة معلومات الاستثناء
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """إعداد نظام السجلات لجميع أجزاء التطبيق."""
    settings = get_settings()

    # إزالة أي معالجات سابقة
    root = logging.getLogger()
    root.handlers.clear()

    # إنشاء معالج stdout بتنسيق JSON
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # تهدئة مكتبات خارجية مزعجة
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
