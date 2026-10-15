"""
نقاط واجهة برمجة التطبيق - إدارة التذاكر والمقاييس والصحة.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.tickets.service import (
    list_tickets,
    get_ticket_by_id,
    get_metrics,
    run_poll_cycle,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────── نماذج الاستجابة ────────────────


class TicketResponse(BaseModel):
    """نموذج استجابة التذكرة لواجهة API."""
    id: str
    created_at: datetime
    updated_at: datetime
    customer_email: str
    subject: str
    thread_id: str
    status: str
    intent: str
    priority: str
    last_inbound_message_id: Optional[str] = None
    last_outbound_message_id: Optional[str] = None
    last_replied_at: Optional[datetime] = None
    confidence: float

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    """نموذج استجابة فحص الصحة."""
    status: str
    timestamp: str
    version: str = "1.0.0-mvp"


class MetricsResponse(BaseModel):
    """نموذج استجابة المقاييس."""
    counters: dict[str, int]
    timestamp: str


class PollResponse(BaseModel):
    """نموذج استجابة تشغيل الاستطلاع."""
    fetched: int
    processed: int
    skipped: int
    errors: int


# ──────────────── نقاط النهاية ────────────────


@router.get("/health", response_model=HealthResponse, tags=["مراقبة"])
async def health_check():
    """
    فحص صحة الخدمة.
    يُرجع حالة التشغيل والطابع الزمني.
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/metrics", response_model=MetricsResponse, tags=["مراقبة"])
async def metrics():
    """
    عرض المقاييس والعدّادات.
    يشمل عدد الاستطلاعات والرسائل والردود والأخطاء.
    """
    return MetricsResponse(
        counters=get_metrics(),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/tickets", response_model=list[TicketResponse], tags=["تذاكر"])
async def list_tickets_endpoint(
    status: Optional[str] = Query(None, description="فلتر حالة التذكرة"),
    intent: Optional[str] = Query(None, description="فلتر نوع النية"),
    priority: Optional[str] = Query(None, description="فلتر الأولوية"),
    limit: int = Query(50, ge=1, le=200, description="عدد النتائج"),
    offset: int = Query(0, ge=0, description="بداية النتائج"),
    db: Session = Depends(get_db),
):
    """
    عرض قائمة التذاكر مع إمكانية التصفية.
    يدعم التصفية حسب: status, intent, priority.
    """
    tickets = list_tickets(
        db=db,
        status=status,
        intent=intent,
        priority=priority,
        limit=limit,
        offset=offset,
    )

    results = []
    for t in tickets:
        results.append(
            TicketResponse(
                id=t.id,
                created_at=t.created_at,
                updated_at=t.updated_at,
                customer_email=t.customer_email,
                subject=t.subject,
                thread_id=t.thread_id,
                status=t.status.value if t.status else "NEW",
                intent=t.intent.value if t.intent else "general",
                priority=t.priority.value if t.priority else "P3",
                last_inbound_message_id=t.last_inbound_message_id,
                last_outbound_message_id=t.last_outbound_message_id,
                last_replied_at=t.last_replied_at,
                confidence=t.confidence,
            )
        )
    return results


@router.get("/tickets/{ticket_id}", response_model=TicketResponse, tags=["تذاكر"])
async def get_ticket_endpoint(
    ticket_id: str,
    db: Session = Depends(get_db),
):
    """جلب تفاصيل تذكرة واحدة بالمعرّف."""
    ticket = get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="التذكرة غير موجودة")

    return TicketResponse(
        id=ticket.id,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        customer_email=ticket.customer_email,
        subject=ticket.subject,
        thread_id=ticket.thread_id,
        status=ticket.status.value if ticket.status else "NEW",
        intent=ticket.intent.value if ticket.intent else "general",
        priority=ticket.priority.value if ticket.priority else "P3",
        last_inbound_message_id=ticket.last_inbound_message_id,
        last_outbound_message_id=ticket.last_outbound_message_id,
        last_replied_at=ticket.last_replied_at,
        confidence=ticket.confidence,
    )


@router.post("/poll", response_model=PollResponse, tags=["تشغيل"])
async def trigger_poll(
    db: Session = Depends(get_db),
):
    """
    تشغيل دورة استطلاع يدوية.
    يجلب الرسائل غير المقروءة ويعالجها.
    """
    try:
        stats = run_poll_cycle(db)
        return PollResponse(**stats)
    except Exception as e:
        logger.exception("فشل في تشغيل دورة الاستطلاع")
        raise HTTPException(status_code=500, detail=str(e))
