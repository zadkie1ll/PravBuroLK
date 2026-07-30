from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import clients, payments_dashboard, search, withdrawals

app = FastAPI(title="Client Search Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5177", "http://127.0.0.1:5177"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(clients.router)
app.include_router(payments_dashboard.router)
app.include_router(withdrawals.router)


@app.get("/health")
def health():
    return {"status": "ok"}
