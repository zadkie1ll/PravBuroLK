from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import redirect, stats

app = FastAPI(title="URL Shortener Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5179", "http://127.0.0.1:5179", "https://panel.prav-buro.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(redirect.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {"status": "ok"}
