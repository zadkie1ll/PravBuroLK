from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import consultation

app = FastAPI(title="Consultation Service", version="0.1.0")

# В проде фронтенд и API живут под одним доменом через nginx (см. deploy/), так что
# CORS там не нужен — это только для локальной разработки, где Vite dev-сервер и
# backend слушают разные порты. Доступ и так закрыт подписанным токеном на каждый
# запрос, поэтому разрешаем любой origin, а не поддерживаем отдельный список.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(consultation.router)


@app.get("/health")
def health():
    return {"status": "ok"}
