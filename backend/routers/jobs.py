"""
Jobs router — queue, status, cancel, logs.
"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.database import get_db
from backend.models import Job, Project
from backend.schemas import JobCreate, JobOut
from backend.services.pipeline import run_pipeline

router = APIRouter()

# In-memory registry of running asyncio tasks keyed by job_id
_running_tasks: dict[str, asyncio.Task] = {}


# ── Create / queue job ────────────────────────────────────────────────────────

@router.post("/", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreate,
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Validate project exists and is ready
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, "Project not found.")
    if project.status not in ("configured", "uploaded", "completed"):
        raise HTTPException(400, "Project must be configured before running a job.")

    job = Job(
        id=str(uuid.uuid4()),
        project_id=project_id,
        mode=payload.mode,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch pipeline as a background task
    background_tasks.add_task(_dispatch_job, job.id, project_id, payload.mode)

    return job


# ── List jobs for a project ───────────────────────────────────────────────────

@router.get("/", response_model=list[JobOut])
def list_jobs(project_id: str, db: Session = Depends(get_db)):
    return (
        db.query(Job)
        .filter(Job.project_id == project_id)
        .order_by(Job.created_at.desc())
        .all()
    )


# ── Get single job ────────────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    return _job_or_404(job_id, db)


# ── Cancel job ────────────────────────────────────────────────────────────────

@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = _job_or_404(job_id, db)
    if job.status not in ("queued", "running"):
        raise HTTPException(400, "Job is not cancellable in its current state.")

    task = _running_tasks.get(job_id)
    if task:
        task.cancel()
        _running_tasks.pop(job_id, None)

    job.status = "cancelled"
    job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


# ── Logs ──────────────────────────────────────────────────────────────────────

@router.get("/{job_id}/logs")
def get_logs(job_id: str, db: Session = Depends(get_db)):
    """Return full log file as plain text."""
    job = _job_or_404(job_id, db)
    log_file = settings.project_path(job.project_id) / "logs" / f"{job_id}.log"
    if not log_file.exists():
        return {"log": "No log output yet."}
    return {"log": log_file.read_text(errors="replace")}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_or_404(job_id: str, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found.")
    return job


def _dispatch_job(job_id: str, project_id: str, mode: str) -> None:
    """Called as a FastAPI background task — runs the pipeline synchronously."""
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        # Run the pipeline
        success, error_msg = run_pipeline(
            project=project,
            job=job,
            db=db,
            mode=mode,
        )

        job.status = "success" if success else "failed"
        job.error_msg = error_msg
        job.finished_at = datetime.utcnow()

        if success:
            project.status = "completed"
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_msg = f"Unexpected error: {exc}"
            job.finished_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
