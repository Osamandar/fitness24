"""Бизнес-логика абонементов."""
from datetime import date

from .models import Client, Membership


def membership_state(m: Membership, today: date) -> str:
    if m.frozen_until and m.frozen_until >= today:
        return "frozen"
    if m.start_date > today:
        return "pending"
    if m.end_date < today:
        return "expired"
    if m.visits_left is not None and m.visits_left <= 0:
        return "exhausted"
    return "active"


STATE_NAMES = {
    "active": "Действует", "frozen": "Заморожен", "pending": "Ещё не начался",
    "expired": "Истёк", "exhausted": "Посещения закончились",
}


def active_membership(client: Client, today: date) -> Membership | None:
    for m in sorted(client.memberships, key=lambda x: x.end_date, reverse=True):
        if membership_state(m, today) == "active":
            return m
    return None
