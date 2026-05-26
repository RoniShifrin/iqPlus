"""Main FastAPI application"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pathlib import Path
import logging
import os
from dotenv import load_dotenv

# Load .env from project root (two levels up from app/)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

import certifi
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models import ALL_DOCUMENTS
from app.api.routes.auth import router as auth_router
from app.api.routes.courses import router as courses_router
from app.api.routes.enrollments import router as enrollments_router
from app.api.routes.academic import router as academic_router
from app.api.routes.progress import router as progress_router
from app.api.routes.profile import router as profile_router, users_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.materials import router as materials_router
from app.api.routes.search import router as search_router
from app.api.routes.audit import router as audit_router
from app.api.routes.lesson_records import router as lesson_records_router
from app.api.routes.ai_alerts import router as ai_alerts_router
from app.api.routes.reports import router as reports_router
from app.api.routes.timeline import router as timeline_router
from app.api.routes.trends import router as trends_router
from app.api.routes.admin_health import router as admin_health_router
from app.api.routes.scores import router as scores_router
from app.api.routes.messages import router as messages_router
from app.api.routes.syllabus import router as syllabus_router
from app.api.routes.usability import router as usability_router
from app.api.routes.admin_demo import router as admin_demo_router
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.ai_insights import router as ai_insights_router
from app.api.routes.chat import router as chat_router
from app.api.routes.parent import router as parent_router
from app.api.routes.academic_planning import router as academic_planning_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "iqplus_db")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to MongoDB (URI prefix: %s...)", MONGODB_URL[:40])
    try:
        client = AsyncIOMotorClient(
            MONGODB_URL,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=15000,
        )
        await init_beanie(database=client[DB_NAME], document_models=ALL_DOCUMENTS)
    except Exception as exc:
        logger.critical("MongoDB connection FAILED: %s", exc)
        raise
    logger.info("IQ PLUS Backend Started")
    from app.services.scheduler import start_scheduler
    start_scheduler()
    yield
    from app.services.scheduler import stop_scheduler
    stop_scheduler()
    client.close()
    logger.info("IQ PLUS Backend Shut Down")


app = FastAPI(
    title="IQ PLUS API",
    description="Learning Center Management System",
    version="1.0.0",
    lifespan=lifespan
)

# Allow all localhost origins in development; restrict in production
if ENVIRONMENT == "development":
    cors_origins = ["*"]
    cors_credentials = False  # credentials not allowed with wildcard
else:
    cors_origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:3000",
        "https://iqplus-prod-3d7o.vercel.app",
        "https://iqplus-prod-3d7o-shifrin-s-projects.vercel.app",
    ]
    cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files (avatars + materials) as static files
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "materials").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(users_router)
app.include_router(dashboard_router)
app.include_router(courses_router)
app.include_router(enrollments_router)
app.include_router(academic_router)
app.include_router(progress_router)
app.include_router(notifications_router)
app.include_router(materials_router)
app.include_router(search_router)
app.include_router(audit_router)
app.include_router(lesson_records_router)
app.include_router(ai_alerts_router)
app.include_router(reports_router)
app.include_router(timeline_router)
app.include_router(trends_router)
app.include_router(admin_health_router)
app.include_router(scores_router)
app.include_router(messages_router)
app.include_router(syllabus_router)
app.include_router(usability_router)
app.include_router(admin_demo_router)
app.include_router(admin_users_router)
app.include_router(ai_insights_router)
app.include_router(chat_router)
app.include_router(parent_router)
app.include_router(academic_planning_router)


# ── Global error handlers ──────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(status_code=404, content={"error": "Not found", "status": 404})

@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.exception("Unhandled server error: %s", exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "status": 500})

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "status": 500})


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/", tags=["root"])
async def root():
    return {"name": "IQ PLUS API", "version": "1.0.0", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
