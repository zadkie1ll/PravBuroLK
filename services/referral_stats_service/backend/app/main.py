from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import stats, visits

app = FastAPI(title="Referral Stats Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5178", "http://127.0.0.1:5178", "https://panel.prav-buro.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stats.router)
app.include_router(visits.router)


@app.get("/health")
def health():
    return {"status": "ok"}
