"""
إعداد محرك قاعدة البيانات وجلسات العمل.
يدعم PostgreSQL في الإنتاج و SQLite في التطوير المحلي.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from app.config import get_settings


def _build_engine():
    """بناء محرك قاعدة البيانات بناءً على الإعدادات."""
    settings = get_settings()
    url = settings.database_url

    # إعدادات خاصة بـ SQLite لدعم الخيوط المتعددة
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        url,
        connect_args=connect_args,
        echo=False,
        pool_pre_ping=True,
    )
    return engine


engine = _build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """الفئة الأساسية لجميع نماذج قاعدة البيانات."""
    pass


def get_db() -> Session:  # type: ignore[misc]
    """مولّد جلسة قاعدة البيانات لاستخدامه كاعتماد في FastAPI."""
    db = SessionLocal()
    try:
        yield db  # type: ignore[misc]
    finally:
        db.close()


def init_db() -> None:
    """إنشاء جميع الجداول إذا لم تكن موجودة."""
    # استيراد النماذج لتسجيلها مع Base.metadata
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
