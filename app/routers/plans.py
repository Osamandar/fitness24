from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_of, get_current_user, require_roles
from ..models import Client, Membership, Payment, Plan, User
from ..schemas import FreezeIn, MembershipIn, MembershipOut, PlanIn, PlanOut
from ..services import STATE_NAMES, membership_state

router = APIRouter(tags=["Тарифы и абонементы"])
admin = require_roles("admin")


def m_out(m: Membership) -> MembershipOut:
    state = membership_state(m, date.today())
    return MembershipOut(id=m.id, client_id=m.client_id, client_name=m.client.full_name, plan_name=m.plan.name,
                         access_mode=m.plan.access_mode, start_date=m.start_date, end_date=m.end_date,
                         visits_left=m.visits_left, frozen_until=m.frozen_until, state=state,
                         state_name=STATE_NAMES[state])


@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.price).all()


@router.post("/plans", response_model=PlanOut, status_code=201)
def create_plan(data: PlanIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    if db.query(Plan).filter(Plan.name == data.name).first():
        raise HTTPException(409, "Тариф с таким названием уже есть")
    plan = Plan(**data.model_dump())
    db.add(plan)
    audit(db, user, "plan_create", data.name)
    db.commit()
    return plan


@router.get("/memberships", response_model=list[MembershipOut])
def list_memberships(client_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(admin)):
    q = db.query(Membership)
    if client_id:
        q = q.filter(Membership.client_id == client_id)
    return [m_out(m) for m in q.order_by(Membership.id.desc()).limit(200)]


@router.post("/memberships", response_model=MembershipOut, status_code=201)
def sell_membership(data: MembershipIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    """Продажа абонемента: создаёт абонемент и фиксирует оплату."""
    client, plan = db.get(Client, data.client_id), db.get(Plan, data.plan_id)
    if client is None or plan is None or not plan.is_active:
        raise HTTPException(404, "Клиент или тариф не найден")
    start = data.start_date or date.today()
    if start < date.today():
        raise HTTPException(400, "Дата начала не может быть в прошлом")
    m = Membership(client_id=client.id, plan_id=plan.id, start_date=start,
                   end_date=start + timedelta(days=plan.duration_days - 1), visits_left=plan.visits_limit)
    db.add(m)
    db.flush()
    db.add(Payment(membership_id=m.id, amount=plan.price, method=data.payment_method))
    audit(db, user, "membership_sell", f"Абонемент #{m.id} «{plan.name}» клиенту #{client.id}, {plan.price} ₽")
    db.commit()
    db.refresh(m)
    return m_out(m)


@router.post("/memberships/{membership_id}/freeze", response_model=MembershipOut)
def freeze(membership_id: int, data: FreezeIn, db: Session = Depends(get_db),
           user: User = Depends(require_roles("admin", "client"))):
    """Заморозка абонемента (один раз, до 30 дней). Срок действия продлевается на число дней заморозки."""
    m = db.get(Membership, membership_id)
    if m is None:
        raise HTTPException(404, "Абонемент не найден")
    if user.role == "client" and m.client_id != get_client_of(user, db).id:
        raise HTTPException(403, "Это не ваш абонемент")
    if m.freeze_used:
        raise HTTPException(400, "Заморозка по этому абонементу уже использована")
    if membership_state(m, date.today()) != "active":
        raise HTTPException(400, "Заморозить можно только действующий абонемент")
    m.frozen_until = date.today() + timedelta(days=data.days - 1)
    m.end_date = m.end_date + timedelta(days=data.days)
    m.freeze_used = True
    audit(db, user, "membership_freeze", f"Абонемент #{m.id} на {data.days} дн.")
    db.commit()
    return m_out(m)


@router.get("/me/memberships", response_model=list[MembershipOut])
def my_memberships(db: Session = Depends(get_db), user: User = Depends(require_roles("client"))):
    client = get_client_of(user, db)
    return [m_out(m) for m in sorted(client.memberships, key=lambda x: x.end_date, reverse=True)]
