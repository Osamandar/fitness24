from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, require_roles
from ..models import Client, User, now
from ..schemas import ClientIn, ClientOut
from ..security import hash_password, password_is_strong
from ..services import active_membership

router = APIRouter(prefix="/clients", tags=["Клиенты"])
staff = require_roles("admin")


def to_out(c: Client) -> ClientOut:
    out = ClientOut.model_validate(c)
    m = active_membership(c, date.today())
    out.membership = f"{m.plan.name} до {m.end_date:%d.%m.%Y}" if m else None
    return out


@router.get("", response_model=list[ClientOut])
def list_clients(q: str = "", db: Session = Depends(get_db), user: User = Depends(staff)):
    query = db.query(Client)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Client.full_name.ilike(like), Client.phone.ilike(like), Client.email.ilike(like)))
    return [to_out(c) for c in query.order_by(Client.full_name).limit(200)]


@router.post("", response_model=ClientOut, status_code=201)
def create_client(data: ClientIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    if not data.pd_consent:
        raise HTTPException(400, "Без согласия клиента на обработку ПДн карточку создать нельзя")
    user_id = None
    if data.password:
        if not data.email:
            raise HTTPException(400, "Для личного кабинета укажите email")
        if not password_is_strong(data.password):
            raise HTTPException(400, "Пароль должен быть не короче 8 символов и содержать буквы и цифры")
        if db.query(User).filter(User.email == data.email.lower()).first():
            raise HTTPException(409, "Пользователь с таким email уже есть")
        account = User(email=data.email.lower(), full_name=data.full_name,
                       password_hash=hash_password(data.password), role="client")
        db.add(account)
        db.flush()
        user_id = account.id
    client = Client(user_id=user_id, full_name=data.full_name, phone=data.phone,
                    email=data.email.lower() if data.email else None, birth_date=data.birth_date,
                    pd_consent=True, consent_at=now())
    db.add(client)
    db.flush()
    audit(db, user, "client_create", f"Клиент #{client.id} {client.full_name}")
    db.commit()
    return to_out(client)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(404, "Клиент не найден")
    return to_out(client)
