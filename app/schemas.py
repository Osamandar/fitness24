"""Схемы входных и выходных данных API (валидация через Pydantic)."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PHONE = r"^\+?\d{10,15}$"
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=1, max_length=128)


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    phone: str = Field(pattern=PHONE)
    email: str = Field(pattern=EMAIL)
    password: str = Field(min_length=8, max_length=128)
    pd_consent: bool


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ClientIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    phone: str = Field(pattern=PHONE)
    email: Optional[str] = Field(default=None, pattern=EMAIL)
    birth_date: Optional[date] = None
    pd_consent: bool
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class ClientOut(ORM):
    id: int
    full_name: str
    phone: str
    email: Optional[str]
    birth_date: Optional[date]
    pd_consent: bool
    created_at: datetime
    membership: Optional[str] = None


class PlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    duration_days: int = Field(gt=0, le=730)
    price: int = Field(ge=0)
    access_mode: Literal["24/7", "day"] = "24/7"
    visits_limit: Optional[int] = Field(default=None, gt=0)


class PlanOut(PlanIn, ORM):
    id: int
    is_active: bool


class MembershipIn(BaseModel):
    client_id: int
    plan_id: int
    start_date: Optional[date] = None
    payment_method: Literal["card", "cash", "online"] = "card"


class MembershipOut(BaseModel):
    id: int
    client_id: int
    client_name: str
    plan_name: str
    access_mode: str
    start_date: date
    end_date: date
    visits_left: Optional[int]
    frozen_until: Optional[date]
    state: str
    state_name: str


class FreezeIn(BaseModel):
    days: int = Field(ge=1, le=30)


class TrainerIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=150)
    specialization: str = Field(min_length=2, max_length=100)
    phone: str = Field(default="", max_length=20)
    email: Optional[str] = Field(default=None, pattern=EMAIL)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class TrainerOut(ORM):
    id: int
    full_name: str
    specialization: str
    phone: str


class ClassIn(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    trainer_id: int
    starts_at: datetime
    duration_min: int = Field(default=60, ge=15, le=240)
    capacity: int = Field(default=15, ge=1, le=100)
    room: str = Field(default="Зал 1", max_length=50)


class ClassOut(BaseModel):
    id: int
    title: str
    trainer_name: str
    starts_at: datetime
    duration_min: int
    capacity: int
    room: str
    booked: int
    is_booked_by_me: bool = False


class AccessCheckIn(BaseModel):
    token: str = Field(min_length=5, max_length=200)
    direction: Literal["in", "out"] = "in"


class AccessResult(BaseModel):
    granted: bool
    reason: str
    client_name: Optional[str] = None


class AccessEventOut(BaseModel):
    id: int
    at: datetime
    client_name: Optional[str]
    direction: str
    granted: bool
    reason: str


class AuditOut(BaseModel):
    id: int
    at: datetime
    user: Optional[str]
    action: str
    details: str
