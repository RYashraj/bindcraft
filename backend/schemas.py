"""
Pydantic schemas for API request/response validation.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, field_validator


# ─── Project ────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    notes: str | None = None


class ProjectSettings(BaseModel):
    """Wizard-collected parameters."""
    # Force fields (v1: locked)
    protein_ff: str = "ff14SB"
    ligand_ff: str = "GAFF2"
    water_model: str = "TIP3P"

    # Solvent
    solvent_type: str = Field("explicit", pattern="^(implicit|explicit)$")
    box_padding: float = Field(10.0, ge=5.0, le=20.0)

    # Conditions
    temperature: float = Field(300.0, ge=200.0, le=400.0)
    pressure: float = Field(1.0, ge=0.5, le=2.0)

    # Simulation preset: fast_test | basic_test
    preset: str = Field("fast_test", pattern="^(fast_test|basic_test)$")

    # Output frequency (steps)
    output_freq: int = Field(500, ge=100, le=5000)

    @field_validator("preset")
    @classmethod
    def preset_params(cls, v: str) -> str:
        return v


class ProjectOut(BaseModel):
    id: str
    name: str
    notes: str | None
    pdb_filename: str | None
    ligand_filename: str | None
    ligand_name: str | None
    ligand_charge: int | None
    status: str
    settings_json: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Job ────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    mode: str = Field(..., pattern="^(generate|run|demo)$")


class JobOut(BaseModel):
    id: str
    project_id: str
    mode: str
    status: str
    current_step: str | None
    error_msg: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


# ─── Validation ─────────────────────────────────────────────────────────────

class ValidationWarning(BaseModel):
    level: str  # info | warning | error
    code: str
    message: str
    detail: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    warnings: list[ValidationWarning]
    residue_count: int | None = None
    atom_count: int | None = None
    ligand_residue: str | None = None
    has_hydrogens: bool | None = None


# ─── System Check ───────────────────────────────────────────────────────────

class SystemCheck(BaseModel):
    wsl_available: bool
    wsl_distro: str | None
    ambertools_available: bool
    tools: dict[str, bool]
    disk_free_gb: float
    python_version: str


# ─── Charts ─────────────────────────────────────────────────────────────────

class ChartData(BaseModel):
    energy: list[dict[str, Any]] = []
    temperature: list[dict[str, Any]] = []
    rmsd: list[dict[str, Any]] = []
    rmsf: list[dict[str, Any]] = []
    rg: list[dict[str, Any]] = []


# ─── File listing ───────────────────────────────────────────────────────────

class FileEntry(BaseModel):
    name: str
    path: str
    size_bytes: int
    category: str  # input | output | logs | analysis | report
