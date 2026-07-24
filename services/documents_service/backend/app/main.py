from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import dogovor

app = FastAPI(title="Documents Service", version="0.1.0")

app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")
app.include_router(dogovor.router)


@app.get("/health")
def health():
    return {"status": "ok"}
