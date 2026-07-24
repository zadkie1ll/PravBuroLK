from fastapi import FastAPI

from .routers import dogovor

app = FastAPI(title="Documents Service", version="0.1.0")

app.include_router(dogovor.router)


@app.get("/health")
def health():
    return {"status": "ok"}
