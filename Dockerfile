# صورة Docker لنظام الرد التلقائي على الشكاوى
# يستخدم Python 3.11 الرسمي كقاعدة

FROM python:3.11-slim

# تعيين متغيرات البيئة
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# إنشاء مستخدم غير جذري للأمان
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --create-home appuser

# تعيين مجلد العمل
WORKDIR /app

# تثبيت الاعتماديات أولاً (للاستفادة من التخزين المؤقت)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كود التطبيق
COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup scripts/ ./scripts/

# إنشاء مجلد للبيانات (token.json, etc)
RUN mkdir -p /app/data && chown appuser:appgroup /app/data

# التبديل للمستخدم غير الجذري
USER appuser

# المنفذ الافتراضي
EXPOSE 8000

# الأمر الافتراضي: تشغيل الخادم
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
