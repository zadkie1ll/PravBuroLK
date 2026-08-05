from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import admin, auth, internal, stats

app = FastAPI(title="Leadreport Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175", "https://panel.prav-buro.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(internal.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
