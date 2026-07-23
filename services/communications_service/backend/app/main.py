from fastapi import FastAPI

from .routers import webhooks

app = FastAPI(title="Communications Service", version="0.1.0")

app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
