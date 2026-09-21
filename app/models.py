"""Модель данных информационной системы «Фитнес-центр 24»."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now() -> datetime:
    return datetime.now()


class User(Base):
    """Учётная запись. Роли: admin (администратор), trainer (тренер), client (клиент)."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Согласие на обработку персональных данных (152-ФЗ)
    pd_consent: Mapped[bool] = mapped_column(default=False)
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="client")


class Trainer(Base):
    __tablename__ = "trainers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(150))
    specialization: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), default="")


class Plan(Base):
    """Тариф абонемента. access_mode: '24/7' — круглосуточно, 'day' — с 07:00 до 23:00."""
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    duration_days: Mapped[int]
    price: Mapped[int]  # в рублях
    access_mode: Mapped[str] = mapped_column(String(10), default="24/7")
    visits_limit: Mapped[Optional[int]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    visits_left: Mapped[Optional[int]] = mapped_column(nullable=True)
    frozen_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    freeze_used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    client: Mapped[Client] = relationship(back_populates="memberships")
    plan: Mapped[Plan] = relationship()


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id"))
    amount: Mapped[int]
    method: Mapped[str] = mapped_column(String(20))
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class GymClass(Base):
    """Групповое занятие в расписании."""
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainers.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_min: Mapped[int] = mapped_column(default=60)
    capacity: Mapped[int] = mapped_column(default=15)
    room: Mapped[str] = mapped_column(String(50), default="Зал 1")
    trainer: Mapped[Trainer] = relationship()
    bookings: Mapped[list["Booking"]] = relationship(back_populates="gym_class", cascade="all, delete-orphan")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("class_id", "client_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    gym_class: Mapped[GymClass] = relationship(back_populates="bookings")
    client: Mapped[Client] = relationship()


class AccessEvent(Base):
    """Журнал проходов через турникет (СКУД)."""
    __tablename__ = "access_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    direction: Mapped[str] = mapped_column(String(3))  # in / out
    granted: Mapped[bool]
    reason: Mapped[str] = mapped_column(String(150), default="")
    client: Mapped[Optional[Client]] = relationship()


class AuditLog(Base):
    """Журнал аудита действий пользователей."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    user: Mapped[Optional[User]] = relationship()
