from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import AccessEvent, AuditLog, Client, GymClass, Membership, Payment, User
from ..schemas import AuditOut
from ..services import membership_state

router = APIRouter(tags=["Отчёты и аудит"])
admin = require_roles("admin")


@router.get("/reports/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(admin)):
    today = date.today()
    day_start = datetime.combine(today, datetime.min.time())
    month_start = datetime.combine(today.replace(day=1), datetime.min.time())
    active = sum(1 for m in db.query(Membership).all() if membership_state(m, today) == "active")
    revenue = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.paid_at >= month_start).scalar()
    # Клуб работает круглосуточно, поэтому «сутки» — это последние 24 часа, а не календарный день
    today_events = db.query(AccessEvent).filter(AccessEvent.at >= datetime.now() - timedelta(hours=24)).all()
    ins = sum(1 for e in today_events if e.granted and e.direction == "in")
    outs = sum(1 for e in today_events if e.granted and e.direction == "out")
    denied = sum(1 for e in today_events if not e.granted)
    hours = [0] * 24
    for e in today_events:
        if e.granted and e.direction == "in":
            hours[e.at.hour] += 1
    upcoming = db.query(GymClass).filter(GymClass.starts_at >= datetime.now(),
                                         GymClass.starts_at < day_start + timedelta(days=1)).count()
    return {
        "clients": db.query(Client).count(), "active_memberships": active, "revenue_month": int(revenue),
        "visits_today": ins, "in_gym_now": max(ins - outs, 0), "denied_today": denied,
        "classes_left_today": upcoming, "visits_by_hour": hours,
    }


@router.get("/audit", response_model=list[AuditOut])
def audit_log(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(admin)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500)).all()
    return [AuditOut(id=a.id, at=a.at, user=a.user.email if a.user else None, action=a.action,
                     details=a.details) for a in rows]
