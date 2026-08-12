"""
BindCraft FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from backend.config import settings
from backend.database import init_db
from backend.routers import projects, jobs, files, system
from backend.services.demo_seeder import seed_demo_project

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("bindcraft")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("BindCraft %s starting up", settings.version)
    settings.ensure_dirs()
    init_db()
    seed_demo_project()
    yield
    logger.info("BindCraft shutting down")


app = FastAPI(
    title="BindCraft API",
    version=settings.version,
    description="AMBER molecular dynamics workflow platform for B.Pharm students.",
    lifespan=lifespan,
)

# ── API routers ──────────────────────────────────────────────────────────────
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(files.router, prefix="/api/projects", tags=["files"])
app.include_router(system.router, prefix="/api/system", tags=["system"])

# ── Static frontend ───────────────────────────────────────────────────────────
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend)), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_spa():
    index = _frontend / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse("<h1>BindCraft</h1><p>Frontend not found.</p>")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.version}
