from fastapi import FastAPI

from .routers import internal, webhooks

app = FastAPI(title="Lead Control Service", version="0.1.0")

app.include_router(webhooks.router)
app.include_router(internal.router)


@app.get("/health")
def health():
    return {"status": "ok"}
