"""
نقطة الدخول الرئيسية لتطبيق FastAPI.
يُعدّ التطبيق ويربط المسارات ويُشغّل المجدول الدوري.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db, SessionLocal
from app.api.routes import router
from app.logging_config import setup_logging
from app.tickets.service import run_poll_cycle

# إعداد السجلات أولاً
setup_logging()
logger = logging.getLogger(__name__)


# ──────────────── المجدول الدوري ────────────────

_poll_task: asyncio.Task | None = None


async def _polling_loop() -> None:
    """
    حلقة استطلاع دورية تعمل في الخلفية.
    تجلب الرسائل غير المقروءة وتعالجها كل N ثانية.
    """
    settings = get_settings()
    interval = settings.poll_interval_seconds
    logger.info("بدء المجدول الدوري (كل %d ثانية)", interval)

    while True:
        try:
            # تشغيل الاستطلاع في خيط منفصل لعدم حجب حلقة الأحداث
            db = SessionLocal()
            try:
                stats = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: run_poll_cycle(db)
                )
                logger.info(
                    "اكتملت دورة الاستطلاع",
                    extra=stats,
                )
            finally:
                db.close()
        except Exception:
            logger.exception("خطأ في دورة الاستطلاع")

        await asyncio.sleep(interval)


# ──────────────── دورة حياة التطبيق ────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    إدارة دورة حياة التطبيق:
    - عند البدء: إنشاء الجداول وبدء المجدول
    - عند الإيقاف: إلغاء المجدول
    """
    global _poll_task

    logger.info("بدء تشغيل التطبيق")

    # إنشاء جداول قاعدة البيانات
    init_db()
    logger.info("تم إعداد قاعدة البيانات")

    # بدء المجدول الدوري
    _poll_task = asyncio.create_task(_polling_loop())
    logger.info("تم بدء المجدول الدوري")

    yield

    # إيقاف المجدول عند إنهاء التطبيق
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    logger.info("تم إيقاف التطبيق")


# ──────────────── إنشاء التطبيق ────────────────

app = FastAPI(
    title="نظام الرد التلقائي على الشكاوى",
    description=(
        "نظام MVP للرد التلقائي على شكاوى البريد الإلكتروني عبر Gmail. "
        "يصنّف الشكاوى ويحاول حلها تلقائيًا."
    ),
    version="1.0.0-mvp",
    lifespan=lifespan,
)

# ربط المسارات
app.include_router(router, prefix="/api")

# مسار جذري للاختبار السريع
@app.get("/", tags=["عام"])
async def root():
    """الصفحة الرئيسية - تأكيد تشغيل الخدمة."""
    return {
        "service": "complaint-auto-reply",
        "version": "1.0.0-mvp",
        "docs": "/docs",
    }
