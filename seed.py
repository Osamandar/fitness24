"""Заполнение базы демонстрационными данными: python seed.py"""
from datetime import date, datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.models import AccessEvent, Client, GymClass, Membership, Payment, Plan, Trainer, User, now
from app.security import hash_password


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(User).first():
        print("База уже заполнена, пропускаю")
        return
    db.add(User(email="admin@fit24.local", full_name="Администратор", role="admin",
                password_hash=hash_password("Admin2026")))

    plans = [Plan(name="Безлимит 24/7 на месяц", duration_days=30, price=3900, access_mode="24/7"),
             Plan(name="Дневной на месяц", duration_days=30, price=2700, access_mode="day"),
             Plan(name="12 посещений", duration_days=60, price=3200, access_mode="24/7", visits_limit=12),
             Plan(name="Безлимит 24/7 на год", duration_days=365, price=32000, access_mode="24/7")]
    db.add_all(plans)

    t_user = User(email="trainer@fit24.local", full_name="Ковалёва Анна Сергеевна", role="trainer",
                  password_hash=hash_password("Trainer2026"))
    db.add(t_user)
    db.flush()
    trainers = [Trainer(user_id=t_user.id, full_name=t_user.full_name, specialization="Йога, пилатес", phone="+79160000001"),
                Trainer(full_name="Громов Илья Петрович", specialization="Функциональный тренинг", phone="+79160000002"),
                Trainer(full_name="Садыков Тимур Ринатович", specialization="Бокс", phone="+79160000003")]
    db.add_all(trainers)

    c_user = User(email="client@fit24.local", full_name="Иванов Пётр Алексеевич", role="client",
                  password_hash=hash_password("Client2026"))
    db.add(c_user)
    db.flush()
    clients = [Client(user_id=c_user.id, full_name=c_user.full_name, phone="+79261112233", email=c_user.email,
                      pd_consent=True, consent_at=now()),
               Client(full_name="Смирнова Елена Викторовна", phone="+79262223344", pd_consent=True, consent_at=now()),
               Client(full_name="Ким Денис Олегович", phone="+79263334455", pd_consent=True, consent_at=now()),
               Client(full_name="Орлова Мария Игоревна", phone="+79264445566", pd_consent=True, consent_at=now())]
    db.add_all(clients)
    db.flush()

    today = date.today()
    for client, plan, shift in [(clients[0], plans[0], 5), (clients[1], plans[1], 10), (clients[2], plans[2], 3),
                                (clients[3], plans[0], 40)]:
        start = today - timedelta(days=shift)
        m = Membership(client_id=client.id, plan_id=plan.id, start_date=start,
                       end_date=start + timedelta(days=plan.duration_days - 1), visits_left=plan.visits_limit)
        db.add(m)
        db.flush()
        db.add(Payment(membership_id=m.id, amount=plan.price, method="card"))

    base = datetime.combine(today, datetime.min.time())
    for day in range(7):
        d = base + timedelta(days=day)
        db.add_all([GymClass(title="Утренняя йога", trainer_id=trainers[0].id, starts_at=d + timedelta(hours=8),
                             capacity=12, room="Зал йоги"),
                    GymClass(title="Функциональная тренировка", trainer_id=trainers[1].id,
                             starts_at=d + timedelta(hours=19), capacity=15, room="Зал 1"),
                    GymClass(title="Ночной бокс", trainer_id=trainers[2].id, starts_at=d + timedelta(hours=22),
                             duration_min=90, capacity=10, room="Ринг")])
    # История проходов за прошедшие сутки для наглядности отчётов
    visits = [(0, 0), (1, 1), (6, 2), (7, 0), (7, 3), (8, 1), (12, 2), (18, 0), (18, 3), (19, 1), (20, 2),
              (22, 3), (23, 0)]
    yesterday = base - timedelta(days=1)
    for hour, idx in visits:
        t_in = yesterday + timedelta(hours=hour, minutes=5 + idx * 7)
        db.add(AccessEvent(client_id=clients[idx].id, at=t_in, direction="in", granted=True, reason="Проход разрешён"))
        db.add(AccessEvent(client_id=clients[idx].id, at=t_in + timedelta(minutes=50), direction="out",
                           granted=True, reason="Выход"))
    db.commit()
    print("Готово. Входы: admin@fit24.local / Admin2026, trainer@fit24.local / Trainer2026, "
          "client@fit24.local / Client2026")


if __name__ == "__main__":
    run()
