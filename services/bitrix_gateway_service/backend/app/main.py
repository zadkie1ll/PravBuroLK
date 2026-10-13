from fastapi import FastAPI
import logging
from contextlib import asynccontextmanager

from .routers import bitrix
from .config import settings
from .modules.lead_phone.runtime import HideWebhookAccess, Runtime
from .modules.lead_phone.router import router as lead_phone_router


@asynccontextmanager
async def lifespan(app):
    app.state.lead_phone = None
    logging.getLogger("uvicorn.access").addFilter(HideWebhookAccess())
    logging.getLogger("lead_phone").setLevel(logging.INFO)
    if settings.lead_phone_enabled:
        try:
            runtime = Runtime(settings)
            await runtime.start()
            app.state.lead_phone = runtime
        except Exception:
            # An optional module must not take the existing gateway down.
            logging.getLogger("lead_phone").error("lead_phone startup_failed")
    try:
        yield
    finally:
        if app.state.lead_phone:
            await app.state.lead_phone.stop()


app = FastAPI(title="Bitrix Gateway Service", version="0.1.0", lifespan=lifespan)

app.include_router(bitrix.router)
app.include_router(lead_phone_router)


@app.get("/health")
def health():
    return {"status": "ok"}
