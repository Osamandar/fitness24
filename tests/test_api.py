import time

from app.security import make_qr_token, verify_qr_token
from tests.conftest import login

DEVICE = {"X-Device-Key": "test-device"}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_wrong_password_and_lockout(client):
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": "trainer@fit24.local", "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": "trainer@fit24.local", "password": "Trainer2026"})
    assert r.status_code == 429


def test_rbac_client_cannot_list_clients(client, member):
    assert client.get("/api/clients", headers=member).status_code == 403
    assert client.get("/api/clients").status_code == 401


def test_register_requires_consent_and_strong_password(client):
    base = {"full_name": "Тестов Тест", "phone": "+79990001122", "email": "t@t.ru", "password": "abc12345"}
    assert client.post("/api/auth/register", json={**base, "pd_consent": False}).status_code == 400
    assert client.post("/api/auth/register", json={**base, "password": "abcdefgh", "pd_consent": True}).status_code == 400
    assert client.post("/api/auth/register", json={**base, "pd_consent": True}).status_code == 201


def test_sell_membership(client, admin):
    c = client.post("/api/clients", headers=admin,
                    json={"full_name": "Новиков Олег", "phone": "+79991234567", "pd_consent": True}).json()
    plans = client.get("/api/plans", headers=admin).json()
    r = client.post("/api/memberships", headers=admin, json={"client_id": c["id"], "plan_id": plans[0]["id"]})
    assert r.status_code == 201
    assert r.json()["state"] == "active"


def test_qr_signature_and_expiry():
    token = make_qr_token(1)
    assert verify_qr_token(token) == 1
    forged = token[:-1] + ("0" if token[-1] != "0" else "1")
    try:
        verify_qr_token(forged)
        assert False
    except ValueError as e:
        assert "Подпись" in str(e)
    old = make_qr_token(1, ts=time.time() - 3600)
    try:
        verify_qr_token(old)
        assert False
    except ValueError as e:
        assert "истёк" in str(e)


def test_turnstile_flow_and_antipassback(client, member):
    token = client.get("/api/me/qr", headers=member).json()["token"]
    assert client.post("/api/access/check", json={"token": token}).status_code == 401
    r = client.post("/api/access/check", headers=DEVICE, json={"token": token, "direction": "in"}).json()
    assert r["granted"] is True
    r = client.post("/api/access/check", headers=DEVICE, json={"token": token, "direction": "in"}).json()
    assert r["granted"] is False and "Повторный" in r["reason"]
    assert client.post("/api/access/check", headers=DEVICE, json={"token": token, "direction": "out"}).json()["granted"]


def test_booking(client, member):
    classes = client.get("/api/classes", headers=member).json()
    future = [c for c in classes if not c["is_booked_by_me"]]
    cls = future[-1]
    assert client.post(f"/api/classes/{cls['id']}/book", headers=member).status_code == 200
    assert client.post(f"/api/classes/{cls['id']}/book", headers=member).status_code == 409
    assert client.delete(f"/api/classes/{cls['id']}/book", headers=member).status_code == 200


def test_summary_and_audit(client, admin):
    s = client.get("/api/reports/summary", headers=admin).json()
    assert s["clients"] >= 4 and len(s["visits_by_hour"]) == 24
    actions = {a["action"] for a in client.get("/api/audit", headers=admin).json()}
    assert {"login", "membership_sell"} <= actions
