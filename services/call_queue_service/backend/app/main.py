from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, megafon_webhook, production_queue

app = FastAPI(title="Call Queue Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(production_queue.router)
app.include_router(megafon_webhook.router)


@app.get("/health")
def health():
    return {"status": "ok"}
