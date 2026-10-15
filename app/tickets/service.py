"""
خدمة التذاكر - إنشاء وتحديث التذاكر، منع التكرار، وإدارة SLA.
تتكامل مع Gmail والمصنّف ومحرك الحل التلقائي.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Ticket,
    MessageLog,
    TicketStatus,
    TicketIntent,
    TicketPriority,
    MessageDirection,
)
from app.rules.classifier import classify, ClassificationResult
from app.rules.guardrails import should_skip_message
from app.autosolve.engine import generate_ack_reply, attempt_autosolve
from app.gmail.sender import send_reply, mark_as_read_and_label
from app.gmail.fetcher import list_unread_message_ids, get_message_detail
from app.gmail.parser import parse_message

logger = logging.getLogger(__name__)

# ──────────────── عدّادات المقاييس البسيطة ────────────────

# عدّادات عامة لنقطة /metrics
_counters: dict[str, int] = {
    "polls_total": 0,
    "messages_fetched": 0,
    "messages_skipped": 0,
    "messages_processed": 0,
    "tickets_created": 0,
    "tickets_updated": 0,
    "replies_sent": 0,
    "replies_failed": 0,
    "autosolve_success": 0,
    "autosolve_needinfo": 0,
    "autosolve_escalated": 0,
    "errors_total": 0,
}


def get_metrics() -> dict[str, int]:
    """إرجاع نسخة من العدّادات الحالية."""
    return dict(_counters)


def _inc(key: str, n: int = 1) -> None:
    """زيادة عدّاد."""
    _counters[key] = _counters.get(key, 0) + n


# ──────────────── إدارة التذاكر ────────────────


def get_or_create_ticket(
    db: Session,
    parsed_msg: dict[str, Any],
    classification: ClassificationResult,
) -> tuple[Ticket, bool]:
    """
    البحث عن تذكرة بنفس thread_id أو إنشاء واحدة جديدة.
    يُرجع (التذكرة، هل_جديدة).
    """
    thread_id = parsed_msg["thread_id"]
    existing = db.query(Ticket).filter(Ticket.thread_id == thread_id).first()

    if existing:
        # تحديث التذكرة الموجودة
        existing.last_inbound_message_id = parsed_msg["message_id"]
        existing.updated_at = datetime.now(timezone.utc)
        # تحديث التصنيف إذا تغير
        if classification.intent != TicketIntent.GENERAL:
            existing.intent = classification.intent
            existing.priority = classification.priority
        db.flush()
        _inc("tickets_updated")
        logger.info(
            "تم تحديث التذكرة",
            extra={"ticket_id": existing.id, "thread_id": thread_id},
        )
        return existing, False

    # إنشاء تذكرة جديدة
    ticket = Ticket(
        customer_email=parsed_msg["sender_email"],
        subject=parsed_msg["subject"],
        thread_id=thread_id,
        status=TicketStatus.NEW,
        intent=classification.intent,
        priority=classification.priority,
        confidence=classification.confidence,
        last_inbound_message_id=parsed_msg["message_id"],
    )
    db.add(ticket)
    db.flush()
    _inc("tickets_created")
    logger.info(
        "تم إنشاء تذكرة جديدة",
        extra={
            "ticket_id": ticket.id,
            "thread_id": thread_id,
            "intent": classification.intent.value,
            "priority": classification.priority.value,
        },
    )
    return ticket, True


def log_message(
    db: Session,
    ticket_id: str,
    message_id: str,
    direction: MessageDirection,
    internal_date: datetime | None,
    raw_headers: dict | None,
    body_clean: str,
) -> MessageLog:
    """تسجيل رسالة في سجل الرسائل."""
    entry = MessageLog(
        ticket_id=ticket_id,
        message_id=message_id,
        direction=direction,
        internal_date=internal_date or datetime.now(timezone.utc),
        raw_headers=raw_headers,
        body_clean=body_clean,
    )
    db.add(entry)
    db.flush()
    return entry


# ──────────────── معالجة رسالة واحدة ────────────────


def process_single_message(
    parsed_msg: dict[str, Any],
    db: Session,
    gmail_user_email: str = "",
) -> bool:
    """
    معالجة رسالة واحدة: التصنيف → التذكرة → الحل التلقائي → الرد → التسمية.
    يُرجع True عند النجاح.
    """
    message_id = parsed_msg["message_id"]
    thread_id = parsed_msg["thread_id"]
    subject = parsed_msg["subject"]
    sender = parsed_msg["sender_email"]
    body = parsed_msg["body_clean"]

    try:
        # 1. فحص الحواجز
        skip, reason = should_skip_message(parsed_msg, db, gmail_user_email)
        if skip:
            logger.info(
                "تم تخطي الرسالة: %s",
                reason,
                extra={"message_id": message_id},
            )
            _inc("messages_skipped")
            return False

        # 2. تصنيف النية
        classification = classify(subject, body)

        # 3. إنشاء / تحديث التذكرة
        ticket, is_new = get_or_create_ticket(db, parsed_msg, classification)

        # 4. تسجيل الرسالة الواردة
        log_message(
            db=db,
            ticket_id=ticket.id,
            message_id=message_id,
            direction=MessageDirection.IN,
            internal_date=parsed_msg.get("internal_date"),
            raw_headers=parsed_msg.get("raw_headers"),
            body_clean=body,
        )

        # 5. تحديث حالة التذكرة إلى AUTO_PROCESSING
        ticket.status = TicketStatus.AUTO_PROCESSING
        db.flush()

        # 6. محاولة الحل التلقائي
        solve_result = attempt_autosolve(classification, ticket.id, subject)

        # 7. إرسال الرد
        sent = send_reply(
            thread_id=thread_id,
            to_email=sender,
            subject=subject,
            body_text=solve_result.reply_body,
            original_message_id_header=parsed_msg.get("gmail_message_id_header", ""),
            references=parsed_msg.get("references", ""),
        )

        if sent:
            sent_id = sent.get("id", "")
            _inc("replies_sent")

            # تسجيل الرسالة الصادرة
            log_message(
                db=db,
                ticket_id=ticket.id,
                message_id=sent_id,
                direction=MessageDirection.OUT,
                internal_date=datetime.now(timezone.utc),
                raw_headers=None,
                body_clean=solve_result.reply_body[:500],
            )

            # تحديث التذكرة
            ticket.status = solve_result.new_status
            ticket.last_outbound_message_id = sent_id
            ticket.last_replied_at = datetime.now(timezone.utc)

            # تحديث العدّادات حسب النتيجة
            if solve_result.new_status == TicketStatus.SOLVED:
                _inc("autosolve_success")
            elif solve_result.new_status == TicketStatus.NEED_INFO:
                _inc("autosolve_needinfo")
            elif solve_result.new_status == TicketStatus.ESCALATED:
                _inc("autosolve_escalated")

            # 8. وسم الرسالة الأصلية (مقروءة + AUTO_REPLIED)
            mark_as_read_and_label(message_id)

            db.commit()
            _inc("messages_processed")

            logger.info(
                "تمت معالجة الرسالة بنجاح",
                extra={
                    "message_id": message_id,
                    "ticket_id": ticket.id,
                    "status": solve_result.new_status.value,
                    "action": solve_result.action_taken,
                },
            )
            return True
        else:
            _inc("replies_failed")
            ticket.status = TicketStatus.ACKED
            db.commit()
            logger.error(
                "فشل في إرسال الرد",
                extra={"message_id": message_id, "ticket_id": ticket.id},
            )
            return False

    except Exception:
        _inc("errors_total")
        db.rollback()
        logger.exception(
            "خطأ أثناء معالجة الرسالة",
            extra={"message_id": message_id},
        )
        return False


# ──────────────── دورة الاستطلاع الكاملة ────────────────


def run_poll_cycle(db: Session, gmail_user_email: str = "") -> dict[str, int]:
    """
    تشغيل دورة استطلاع واحدة: جلب الرسائل → معالجة كل واحدة.
    يُرجع إحصائيات الدورة.
    """
    _inc("polls_total")
    stats = {"fetched": 0, "processed": 0, "skipped": 0, "errors": 0}

    logger.info("بدء دورة استطلاع جديدة")

    # جلب قائمة الرسائل غير المقروءة
    unread = list_unread_message_ids()
    stats["fetched"] = len(unread)
    _inc("messages_fetched", len(unread))

    if not unread:
        logger.info("لا توجد رسائل غير مقروءة")
        return stats

    for msg_stub in unread:
        msg_id = msg_stub.get("id", "")
        if not msg_id:
            continue

        # جلب تفاصيل الرسالة
        raw_msg = get_message_detail(msg_id)
        if not raw_msg:
            stats["errors"] += 1
            continue

        # تحليل الرسالة
        parsed = parse_message(raw_msg)

        # معالجة الرسالة
        ok = process_single_message(parsed, db, gmail_user_email)
        if ok:
            stats["processed"] += 1
        else:
            stats["skipped"] += 1

    logger.info(
        "انتهت دورة الاستطلاع",
        extra=stats,
    )
    return stats


# ──────────────── استعلامات التذاكر ────────────────


def list_tickets(
    db: Session,
    status: str | None = None,
    intent: str | None = None,
    priority: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Ticket]:
    """جلب قائمة التذاكر مع فلاتر اختيارية."""
    query = db.query(Ticket)

    if status:
        try:
            query = query.filter(Ticket.status == TicketStatus(status))
        except ValueError:
            pass

    if intent:
        try:
            query = query.filter(Ticket.intent == TicketIntent(intent))
        except ValueError:
            pass

    if priority:
        try:
            query = query.filter(Ticket.priority == TicketPriority(priority))
        except ValueError:
            pass

    return (
        query
        .order_by(Ticket.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_ticket_by_id(db: Session, ticket_id: str) -> Ticket | None:
    """جلب تذكرة واحدة بالمعرّف."""
    return db.query(Ticket).filter(Ticket.id == ticket_id).first()
