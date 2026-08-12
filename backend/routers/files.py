"""
Files router — list, serve, download ZIP, charts.
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.config import settings
from backend.schemas import ChartData, FileEntry
from backend.services.analyzer import load_chart_data
from backend.services.zip_builder import build_zip

router = APIRouter()

_CATEGORIES = {
    "input": "input",
    "output": "output",
    "logs": "logs",
    "analysis": "analysis",
    "report": "report",
}


@router.get("/{project_id}/files", response_model=list[FileEntry])
def list_files(project_id: str):
    project_dir = settings.project_path(project_id)
    if not project_dir.exists():
        raise HTTPException(404, "Project directory not found.")

    entries: list[FileEntry] = []
    for cat, subdir in _CATEGORIES.items():
        folder = project_dir / subdir
        if folder.exists():
            for f in sorted(folder.iterdir()):
                if f.is_file():
                    entries.append(
                        FileEntry(
                            name=f.name,
                            path=f"/{cat}/{f.name}",
                            size_bytes=f.stat().st_size,
                            category=cat,
                        )
                    )
    return entries


@router.get("/{project_id}/files/{category}/{filename}")
def serve_file(project_id: str, category: str, filename: str):
    if category not in _CATEGORIES:
        raise HTTPException(400, "Invalid category.")
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename.")
    path = settings.project_path(project_id) / category / filename
    if not path.exists():
        raise HTTPException(404, "File not found.")
    return FileResponse(str(path), filename=filename)


@router.get("/{project_id}/charts", response_model=ChartData)
def get_charts(project_id: str):
    project_dir = settings.project_path(project_id)
    if not project_dir.exists():
        raise HTTPException(404, "Project not found.")
    return load_chart_data(project_dir)


@router.get("/{project_id}/download")
def download_zip(project_id: str):
    project_dir = settings.project_path(project_id)
    if not project_dir.exists():
        raise HTTPException(404, "Project not found.")
    zip_path = build_zip(project_dir, project_id)
    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=f"bindcraft_{project_id[:8]}.zip",
    )
