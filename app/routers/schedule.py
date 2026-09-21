from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_of, get_current_user, require_roles
from ..models import Booking, GymClass, Trainer, User
from ..schemas import ClassIn, ClassOut, TrainerIn, TrainerOut
from ..security import hash_password, password_is_strong
from ..services import active_membership

router = APIRouter(tags=["Тренеры и расписание"])
admin = require_roles("admin")


def c_out(c: GymClass, client_id: int | None = None) -> ClassOut:
    return ClassOut(id=c.id, title=c.title, trainer_name=c.trainer.full_name, starts_at=c.starts_at,
                    duration_min=c.duration_min, capacity=c.capacity, room=c.room, booked=len(c.bookings),
                    is_booked_by_me=any(b.client_id == client_id for b in c.bookings) if client_id else False)


@router.get("/trainers", response_model=list[TrainerOut])
def list_trainers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Trainer).order_by(Trainer.full_name).all()


@router.post("/trainers", response_model=TrainerOut, status_code=201)
def create_trainer(data: TrainerIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    user_id = None
    if data.email and data.password:
        if not password_is_strong(data.password):
            raise HTTPException(400, "Пароль должен быть не короче 8 символов и содержать буквы и цифры")
        if db.query(User).filter(User.email == data.email.lower()).first():
            raise HTTPException(409, "Пользователь с таким email уже есть")
        acc = User(email=data.email.lower(), full_name=data.full_name,
                   password_hash=hash_password(data.password), role="trainer")
        db.add(acc)
        db.flush()
        user_id = acc.id
    t = Trainer(user_id=user_id, full_name=data.full_name, specialization=data.specialization, phone=data.phone)
    db.add(t)
    audit(db, user, "trainer_create", data.full_name)
    db.commit()
    return t


@router.get("/classes", response_model=list[ClassOut])
def list_classes(days: int = 7, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    start = datetime.combine(date.today(), datetime.min.time())
    q = db.query(GymClass).filter(GymClass.starts_at >= start,
                                  GymClass.starts_at < start + timedelta(days=min(days, 31)))
    client_id = None
    if user.role == "trainer":
        trainer = db.query(Trainer).filter(Trainer.user_id == user.id).first()
        q = q.filter(GymClass.trainer_id == (trainer.id if trainer else -1))
    elif user.role == "client":
        client_id = get_client_of(user, db).id
    return [c_out(c, client_id) for c in q.order_by(GymClass.starts_at)]


@router.post("/classes", response_model=ClassOut, status_code=201)
def create_class(data: ClassIn, db: Session = Depends(get_db), user: User = Depends(admin)):
    if db.get(Trainer, data.trainer_id) is None:
        raise HTTPException(404, "Тренер не найден")
    end = data.starts_at + timedelta(minutes=data.duration_min)
    # Проверка пересечений: у тренера не может быть двух занятий одновременно
    for other in db.query(GymClass).filter(GymClass.trainer_id == data.trainer_id).all():
        if other.starts_at < end and data.starts_at < other.starts_at + timedelta(minutes=other.duration_min):
            raise HTTPException(409, f"У тренера уже есть занятие «{other.title}» в это время")
    c = GymClass(**data.model_dump())
    db.add(c)
    db.flush()
    audit(db, user, "class_create", f"{c.title} {c.starts_at:%d.%m %H:%M}")
    db.commit()
    db.refresh(c)
    return c_out(c)


@router.post("/classes/{class_id}/book", response_model=ClassOut)
def book(class_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("client"))):
    client = get_client_of(user, db)
    c = db.get(GymClass, class_id)
    if c is None:
        raise HTTPException(404, "Занятие не найдено")
    if c.starts_at <= datetime.now():
        raise HTTPException(400, "Занятие уже началось")
    if active_membership(client, c.starts_at.date()) is None and active_membership(client, date.today()) is None:
        raise HTTPException(400, "Для записи нужен действующий абонемент")
    if any(b.client_id == client.id for b in c.bookings):
        raise HTTPException(409, "Вы уже записаны на это занятие")
    if len(c.bookings) >= c.capacity:
        raise HTTPException(409, "Свободных мест нет")
    db.add(Booking(class_id=c.id, client_id=client.id))
    audit(db, user, "class_book", f"{c.title} {c.starts_at:%d.%m %H:%M}")
    db.commit()
    db.refresh(c)
    return c_out(c, client.id)


@router.delete("/classes/{class_id}/book", response_model=ClassOut)
def cancel_booking(class_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("client"))):
    client = get_client_of(user, db)
    b = db.query(Booking).filter(Booking.class_id == class_id, Booking.client_id == client.id).first()
    if b is None:
        raise HTTPException(404, "Запись не найдена")
    c = b.gym_class
    db.delete(b)
    audit(db, user, "class_cancel", f"{c.title} {c.starts_at:%d.%m %H:%M}")
    db.commit()
    db.refresh(c)
    return c_out(c, client.id)


@router.get("/classes/{class_id}/attendees", response_model=list[str])
def attendees(class_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "trainer"))):
    c = db.get(GymClass, class_id)
    if c is None:
        raise HTTPException(404, "Занятие не найдено")
    if user.role == "trainer":
        trainer = db.query(Trainer).filter(Trainer.user_id == user.id).first()
        if trainer is None or trainer.id != c.trainer_id:
            raise HTTPException(403, "Это не ваше занятие")
    return [b.client.full_name for b in c.bookings]
