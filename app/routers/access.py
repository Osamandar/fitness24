"""Контроль доступа (СКУД): выдача QR-кода клиенту и проверка на турникете."""
import hmac
from datetime import date, datetime, timedelta

import segno
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import bearer, get_client_of, get_current_user, require_roles
from ..models import AccessEvent, Client, User
from ..schemas import AccessCheckIn, AccessEventOut, AccessResult
from ..security import make_qr_token, verify_qr_token
from ..services import active_membership

router = APIRouter(tags=["Контроль доступа"])


@router.get("/me/qr")
def my_qr(db: Session = Depends(get_db), user: User = Depends(require_roles("client"))):
    """Динамический QR-код для прохода. Действует QR_TTL_SECONDS секунд."""
    client = get_client_of(user, db)
    token = make_qr_token(client.id)
    svg = segno.make(token, error="m").svg_inline(scale=6, dark="#0F1B33", light="#FFFFFF")
    return {"token": token, "svg": svg, "ttl": settings.qr_ttl_seconds}


def turnstile_auth(x_device_key: str | None = Header(default=None), creds=Depends(bearer),
                   db: Session = Depends(get_db)) -> str:
    """Турникет авторизуется ключом устройства; администратор — своим токеном (эмулятор в интерфейсе)."""
    if x_device_key and hmac.compare_digest(x_device_key, settings.device_key):
        return "device"
    if creds:
        user = get_current_user(creds, db)
        if user.role == "admin":
            return "admin"
    raise HTTPException(401, "Устройство не авторизовано")


def _log(db: Session, client: Client | None, direction: str, granted: bool, reason: str) -> AccessResult:
    db.add(AccessEvent(client_id=client.id if client else None, direction=direction, granted=granted, reason=reason))
    db.commit()
    return AccessResult(granted=granted, reason=reason, client_name=client.full_name if client else None)


def check_access(db: Session, token: str, direction: str, when: datetime | None = None) -> AccessResult:
    when = when or datetime.now()
    try:
        client_id = verify_qr_token(token)
    except ValueError as e:
        return _log(db, None, direction, False, str(e))
    client = db.get(Client, client_id)
    if client is None:
        return _log(db, None, direction, False, "Клиент не найден")

    last = (db.query(AccessEvent)
            .filter(AccessEvent.client_id == client.id, AccessEvent.granted.is_(True))
            .order_by(AccessEvent.at.desc(), AccessEvent.id.desc()).first())
    if direction == "out":
        return _log(db, client, "out", True, "Выход")

    # Anti-passback: нельзя войти повторно, не выйдя (защита от передачи QR-кода)
    if last and last.direction == "in" and when - last.at < timedelta(hours=12):
        return _log(db, client, "in", False, "Повторный вход без выхода")
    m = active_membership(client, when.date())
    if m is None:
        return _log(db, client, "in", False, "Нет действующего абонемента")
    if m.plan.access_mode == "day" and not (settings.day_open_hour <= when.hour < settings.day_close_hour):
        return _log(db, client, "in", False, "Тариф не даёт доступа в ночное время")
    if m.visits_left is not None:
        m.visits_left -= 1
    return _log(db, client, "in", True, f"Проход разрешён, абонемент «{m.plan.name}» до {m.end_date:%d.%m.%Y}")


@router.post("/access/check", response_model=AccessResult)
def access_check(data: AccessCheckIn, db: Session = Depends(get_db), source: str = Depends(turnstile_auth)):
    return check_access(db, data.token, data.direction)


@router.get("/access/events", response_model=list[AccessEventOut])
def events(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    rows = db.query(AccessEvent).order_by(AccessEvent.id.desc()).limit(min(limit, 500)).all()
    return [AccessEventOut(id=e.id, at=e.at, client_name=e.client.full_name if e.client else None,
                           direction=e.direction, granted=e.granted, reason=e.reason) for e in rows]
