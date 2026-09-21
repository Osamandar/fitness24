import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["DEVICE_KEY"] = "test-device"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
import seed  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        seed.run()
        yield c


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return login(client, "admin@fit24.local", "Admin2026")


@pytest.fixture(scope="session")
def member(client):
    return login(client, "client@fit24.local", "Client2026")
