"""
Projects router — CRUD and file upload.
"""
import json
import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import Project
from backend.schemas import ProjectCreate, ProjectOut, ProjectSettings, ValidationResult
from backend.services.validator import validate_project_files

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB per file


# ── List projects ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


# ── Create project ────────────────────────────────────────────────────────────

@router.post("/", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        id=str(uuid.uuid4()),
        name=payload.name.strip(),
        notes=payload.notes,
        status="new",
    )
    # Create folder structure
    for sub in ("input", "output", "logs", "analysis", "report"):
        (settings.project_path(project.id) / sub).mkdir(parents=True, exist_ok=True)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


# ── Get project ───────────────────────────────────────────────────────────────

@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = _get_or_404(project_id, db)
    return project


# ── Delete project ────────────────────────────────────────────────────────────

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = _get_or_404(project_id, db)
    # Remove files
    project_dir = settings.project_path(project_id)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    db.delete(project)
    db.commit()


# ── Upload files ──────────────────────────────────────────────────────────────

@router.post("/{project_id}/upload", response_model=ValidationResult)
async def upload_files(
    project_id: str,
    pdb_file: Annotated[UploadFile | None, File()] = None,
    ligand_file: Annotated[UploadFile | None, File()] = None,
    ligand_charge: Annotated[int, Form()] = 0,
    db: Session = Depends(get_db),
):
    project = _get_or_404(project_id, db)
    input_dir = settings.project_path(project_id) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    saved_pdb: Path | None = None
    saved_lig: Path | None = None

    if pdb_file:
        _check_extension(pdb_file.filename, [".pdb"])
        saved_pdb = await _save_upload(pdb_file, input_dir)
        project.pdb_filename = pdb_file.filename

    if ligand_file:
        _check_extension(ligand_file.filename, [".sdf", ".mol2"])
        saved_lig = await _save_upload(ligand_file, input_dir)
        project.ligand_filename = ligand_file.filename

    project.ligand_charge = ligand_charge
    project.status = "uploaded"
    db.commit()

    # Validate
    result = validate_project_files(
        pdb_path=saved_pdb,
        ligand_path=saved_lig,
        charge=ligand_charge,
    )

    if result.ligand_residue:
        project.ligand_name = result.ligand_residue
        db.commit()

    return result


# ── Save wizard settings ──────────────────────────────────────────────────────

@router.put("/{project_id}/settings", response_model=ProjectOut)
def save_settings(
    project_id: str,
    payload: ProjectSettings,
    db: Session = Depends(get_db),
):
    project = _get_or_404(project_id, db)
    project.settings_json = payload.model_dump_json()
    project.status = "configured"
    db.commit()
    db.refresh(project)
    return project


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return project


def _check_extension(filename: str | None, allowed: list[str]) -> None:
    if not filename:
        raise HTTPException(status_code=400, detail="File must have a name.")
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(allowed)}",
        )


async def _save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    dest = dest_dir / Path(upload.filename).name
    content = await upload.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")
    dest.write_bytes(content)
    return dest
