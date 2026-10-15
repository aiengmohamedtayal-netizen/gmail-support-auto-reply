# 📧 نظام الرد التلقائي على شكاوى البريد الإلكتروني

> نظام MVP للرد التلقائي على شكاوى العملاء عبر Gmail - يصنّف الشكاوى ويحاول حلها تلقائيًا.

## 🌟 المميزات

- ✅ استطلاع Gmail كل N دقيقة للرسائل غير المقروءة
- ✅ تصنيف الشكاوى تلقائيًا (تتبع شحنة، فاتورة، عام)
- ✅ حل تلقائي لطلبات التتبع وإعادة إرسال الفواتير
- ✅ إرسال ردود في نفس سلسلة البريد
- ✅ منع الحلقات والتكرار
- ✅ سجلات مهيكلة بتنسيق JSON
- ✅ نقاط نهاية للصحة والمقاييس
- ✅ واجهة إدارة للتذاكر
- ✅ Docker + docker-compose

---

## 📋 المتطلبات

- Python 3.11+
- PostgreSQL 15+ (أو SQLite للتطوير المحلي)
- حساب Google Cloud مع Gmail API مفعّل
- Docker & Docker Compose (اختياري)

---

## 🔧 إعداد Google Cloud و Gmail API

### الخطوة 1: إنشاء مشروع Google Cloud

1. اذهب إلى [Google Cloud Console](https://console.cloud.google.com/)
2. انقر على **Select a project** → **New Project**
3. اختر اسمًا للمشروع (مثل: `complaint-auto-reply`)
4. انقر **Create**

### الخطوة 2: تفعيل Gmail API

1. في القائمة الجانبية: **APIs & Services** → **Library**
2. ابحث عن `Gmail API`
3. انقر عليها ثم **Enable**

### الخطوة 3: إعداد شاشة الموافقة OAuth

1. اذهب إلى **APIs & Services** → **OAuth consent screen**
2. اختر **External** (أو Internal إذا كان لديك Google Workspace)
3. املأ الحقول المطلوبة:
   - **App name**: نظام الرد التلقائي
   - **User support email**: بريدك
   - **Developer contact**: بريدك
4. انقر **Save and Continue**
5. في **Scopes**، انقر **Add or Remove Scopes** وأضف:
   ```
   https://www.googleapis.com/auth/gmail.modify
   https://www.googleapis.com/auth/gmail.labels
   ```
6. في **Test users**، أضف بريد Gmail الذي ستستخدمه
7. انقر **Save and Continue** حتى النهاية

### الخطوة 4: إنشاء بيانات اعتماد OAuth

1. اذهب إلى **APIs & Services** → **Credentials**
2. انقر **Create Credentials** → **OAuth client ID**
3. اختر **Desktop app** كنوع التطبيق
4. اختر اسمًا (مثل: `complaint-cli`)
5. انقر **Create**
6. انقر **Download JSON** لتحميل ملف `credentials.json`
7. **انسخ الملف إلى مجلد المشروع** أو إلى `./data/credentials.json`

### الخطوة 5: المصادقة الأولية

عند تشغيل التطبيق لأول مرة:

```bash
# تشغيل محلي
python -m scripts.poll_once
```

سيفتح المتصفح لتسجيل الدخول بحساب Gmail. بعد الموافقة، سيُحفظ `token.json` تلقائيًا.

---

## 🚀 التشغيل

### التشغيل المحلي (SQLite)

```bash
# 1. نسخ ملف البيئة
cp .env.example .env

# 2. تثبيت الاعتماديات
pip install -r requirements.txt

# 3. وضع credentials.json في المجلد الحالي

# 4. تشغيل الخادم
uvicorn app.main:app --reload --port 8000

# أو تشغيل دورة استطلاع واحدة
python -m scripts.poll_once
```

### التشغيل بـ Docker Compose (PostgreSQL)

```bash
# 1. نسخ ملف البيئة
cp .env.example .env
# عدّل .env وأضف GOOGLE_CLIENT_ID و GOOGLE_CLIENT_SECRET

# 2. إنشاء مجلد البيانات
mkdir -p data
cp credentials.json data/

# 3. المصادقة الأولية (محلياً لإنشاء token.json)
python -m scripts.poll_once
cp token.json data/

# 4. بناء وتشغيل الحاويات
docker-compose up --build

# مع Redis (اختياري)
docker-compose --profile with-redis up --build
```

---

## 📡 نقاط النهاية API

| النقطة | الوصف |
|--------|-------|
| `GET /` | الصفحة الرئيسية |
| `GET /docs` | توثيق Swagger التفاعلي |
| `GET /api/health` | فحص صحة الخدمة |
| `GET /api/metrics` | عرض المقاييس والعدّادات |
| `GET /api/tickets` | قائمة التذاكر (مع فلاتر) |
| `GET /api/tickets/{id}` | تفاصيل تذكرة |
| `POST /api/poll` | تشغيل دورة استطلاع يدوية |

### أمثلة الاستخدام

```bash
# فحص الصحة
curl http://localhost:8000/api/health

# عرض المقاييس
curl http://localhost:8000/api/metrics

# قائمة التذاكر
curl http://localhost:8000/api/tickets

# فلترة التذاكر
curl "http://localhost:8000/api/tickets?status=NEW&priority=P1"

# تشغيل استطلاع يدوي
curl -X POST http://localhost:8000/api/poll
```

---

## 📧 أمثلة رسائل الاختبار

### مثال 1: تتبع شحنة (مع رقم الطلب)

**الموضوع:** أين شحنتي؟

**الجسم:**
```
مرحبا،
أريد معرفة حالة طلبي رقم #123456
تأخر كثيراً ولم يصلني بعد.
شكراً
```

**النتيجة المتوقعة:**
- التصنيف: `tracking_update` / `P2`
- الحالة: `SOLVED`
- الرد: رسالة بحالة التتبع ورابط التتبع

---

### مثال 2: تتبع شحنة (بدون رقم الطلب)

**الموضوع:** شحنتي لم تصل

**الجسم:**
```
السلام عليكم
طلبت منتج من عندكم ولم يصلني حتى الآن
```

**النتيجة المتوقعة:**
- التصنيف: `tracking_update` / `P2`
- الحالة: `NEED_INFO`
- الرد: طلب رقم الطلب

---

### مثال 3: إعادة إرسال فاتورة

**الموضوع:** أريد فاتورة

**الجسم:**
```
أحتاج نسخة من الفاتورة رقم #789012 للمحاسبة
```

**النتيجة المتوقعة:**
- التصنيف: `invoice_resend` / `P2`
- الحالة: `SOLVED`
- الرد: رابط تحميل الفاتورة

---

### مثال 4: شكوى عاجلة

**الموضوع:** عاجل - احتيال

**الجسم:**
```
تم سحب مبلغ من حسابي بدون علمي
هذا احتيال وسأتخذ إجراءات قانونية
```

**النتيجة المتوقعة:**
- التصنيف: `general` / `P1`
- الحالة: `ESCALATED`
- الرد: تأكيد استلام + تحويل لفريق متخصص

---

### مثال 5: استفسار عام

**الموضوع:** استفسار

**الجسم:**
```
ما هي ساعات العمل لديكم؟
```

**النتيجة المتوقعة:**
- التصنيف: `general` / `P3`
- الحالة: `ESCALATED`
- الرد: تأكيد استلام + تحويل لفريق الدعم

---

## 🔒 الأمان

- ❌ لا يُطلب أبدًا كلمات المرور أو OTP أو CVV
- 🔐 البيانات الحساسة تُنقّح من السجلات
- ⚡ حد أقصى 50 رد/ساعة (قابل للتعديل)
- 🚫 قوائم النطاقات المسموحة/المحظورة

---

## 📁 هيكل المشروع

```
.
├── app/
│   ├── __init__.py
│   ├── main.py              # نقطة الدخول FastAPI
│   ├── config.py            # إعدادات البيئة
│   ├── db.py                # محرك قاعدة البيانات
│   ├── models.py            # نماذج SQLAlchemy
│   ├── logging_config.py    # إعداد السجلات JSON
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # نقاط النهاية
│   ├── gmail/
│   │   ├── __init__.py
│   │   ├── client.py        # عميل OAuth
│   │   ├── fetcher.py       # جلب الرسائل
│   │   ├── parser.py        # تحليل الرسائل
│   │   └── sender.py        # إرسال الردود
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── guardrails.py    # حواجز الأمان
│   │   └── classifier.py    # مصنّف النوايا
│   ├── autosolve/
│   │   ├── __init__.py
│   │   └── engine.py        # محرك الحل التلقائي
│   └── tickets/
│       ├── __init__.py
│       └── service.py       # خدمة التذاكر
├── scripts/
│   ├── __init__.py
│   └── poll_once.py         # CLI لدورة استطلاع واحدة
├── data/                    # مجلد البيانات (credentials, token)
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🔮 التطوير المستقبلي

- [ ] تصنيف بالذكاء الاصطناعي (OpenAI/Claude)
- [ ] تكاملات حقيقية مع أنظمة الشحن والفواتير
- [ ] واجهة مستخدم لإدارة التذاكر
- [ ] طوابير Redis للمعالجة غير المتزامنة
- [ ] دعم لغات متعددة
- [ ] تقارير وإحصائيات متقدمة

---

## 📜 الترخيص

هذا المشروع للاستخدام الداخلي والتعليمي.
