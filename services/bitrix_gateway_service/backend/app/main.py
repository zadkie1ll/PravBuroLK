from fastapi import FastAPI

from .routers import bitrix

app = FastAPI(title="Bitrix Gateway Service", version="0.1.0")

app.include_router(bitrix.router)


@app.get("/health")
def health():
    return {"status": "ok"}
