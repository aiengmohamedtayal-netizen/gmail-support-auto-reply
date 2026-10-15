"""
سكربت CLI لتشغيل دورة استطلاع واحدة يدويًا.
مفيد للاختبار والتشخيص بدون تشغيل الخادم الكامل.

الاستخدام:
    python -m scripts.poll_once
"""

from __future__ import annotations

import sys
import os

# إضافة المجلد الجذر لمسار الاستيراد
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging
from app.db import init_db, SessionLocal
from app.tickets.service import run_poll_cycle, get_metrics

import logging


def main():
    """تشغيل دورة استطلاع واحدة وطباعة النتائج."""
    # إعداد السجلات
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("═" * 50)
    logger.info("بدء دورة استطلاع يدوية")
    logger.info("═" * 50)

    # إنشاء الجداول إذا لم تكن موجودة
    init_db()

    # فتح جلسة قاعدة البيانات
    db = SessionLocal()
    try:
        stats = run_poll_cycle(db)

        print("\n" + "═" * 50)
        print("📊 نتائج دورة الاستطلاع:")
        print(f"   📨 رسائل مجلوبة:   {stats['fetched']}")
        print(f"   ✅ رسائل معالجة:   {stats['processed']}")
        print(f"   ⏭️  رسائل متخطاة:  {stats['skipped']}")
        print(f"   ❌ أخطاء:          {stats['errors']}")
        print("═" * 50)

        # طباعة المقاييس الكاملة
        metrics = get_metrics()
        print("\n📈 المقاييس التراكمية:")
        for key, val in metrics.items():
            print(f"   {key}: {val}")
        print("═" * 50)

    except Exception:
        logger.exception("فشل في تشغيل دورة الاستطلاع")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
