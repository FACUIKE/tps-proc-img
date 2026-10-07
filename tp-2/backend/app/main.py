from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from docscan import ScanError

from app.config import FRONTEND_DIR, MEDIA_URL, STORAGE_DIR
from app.routers import detect, scan


@asynccontextmanager
async def lifespan(app: FastAPI):
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Document Scanner — TP 2",
    description="API that turns a photo of a document into a clean, straight scan.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ScanError)
async def scan_error_handler(request, exc: ScanError):
    status_code = {"FILE_TOO_LARGE": 413, "DOCUMENT_NOT_FOUND": 422}.get(exc.code, 400)
    return JSONResponse(status_code=status_code, content={"detail": {"code": exc.code, "message": str(exc)}})

# Allows opening the frontend from another origin (e.g. Live Server on :5500).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["system"], summary="Server status")
def health():
    return {"status": "ok"}


app.include_router(detect.router)
app.include_router(scan.router)


# Files stored on disk (scans and original photos).
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount(MEDIA_URL, StaticFiles(directory=STORAGE_DIR), name="media")

# Frontend (must be mounted last because it captures "/").
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
