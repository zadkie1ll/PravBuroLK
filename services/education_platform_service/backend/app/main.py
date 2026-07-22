from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, courses, files, hr

app = FastAPI(title="Education Platform Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(files.router)
app.include_router(hr.router)


@app.get("/health")
def health():
    return {"status": "ok"}
