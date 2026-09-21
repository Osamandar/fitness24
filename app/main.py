"""Информационная система управления круглосуточным фитнес-центром «Фитнес-центр 24»."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import access, auth, clients, plans, reports, schedule


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Фитнес-центр 24", version="1.0.0",
              description="ИС управления круглосуточным фитнес-центром: клиенты, абонементы, "
                          "расписание, контроль доступа по QR-коду, отчёты и аудит.",
              lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com")
    return response


for r in (auth.router, clients.router, plans.router, schedule.router, access.router, reports.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["Служебное"])
def health():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
