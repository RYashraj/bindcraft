"""
Pipeline service — orchestrates the full AmberTools workflow.

Steps for "run" mode:
  1. pdb4amber      — clean PDB, add hydrogens
  2. antechamber    — ligand parameterisation (GAFF2, AM1-BCC charges)
  3. parmchk2       — generate missing parameters (frcmod)
  4. tleap          — build topology + coordinates
  5. sander         — minimization → heating → equilibration → production
  6. cpptraj        — RMSD, RMSF, Rg, energy extraction

For "generate" mode, only steps 1–4 are run (or just rendered if no WSL).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import Job, Project
from backend.schemas import ProjectSettings
from backend.services import template_engine, wsl_runner

logger = logging.getLogger("bindcraft.pipeline")

# Plain-English error map: pattern in stderr → user message
_ERROR_MAP: list[tuple[str, str]] = [
    ("Cannot determine", "antechamber could not determine atom types. Check the ligand structure and net charge."),
    ("FATAL", "A fatal AMBER error occurred. See the log for details."),
    ("Segmentation fault", "The program crashed (segfault). Your system may be out of memory, or the input is malformed."),
    ("could not be assigned", "Some atoms could not be assigned parameters. Try a different net charge or check for unusual elements."),
    ("ERROR: Atom", "tleap found an unrecognised atom or residue. Ensure the protein has no non-standard residues without parameters."),
    ("differing number", "Coordinate/topology mismatch. Likely a tleap error — check the tleap log carefully."),
    ("out of memory", "Simulation ran out of memory. Try switching to implicit solvent or a smaller system."),
]


def run_pipeline(
    project: Project,
    job: Job,
    db: Session,
    mode: str,
) -> tuple[bool, str | None]:
    """
    Run the full pipeline.
    Returns (success: bool, error_message: str | None).
    """
    project_dir = settings.project_path(project.id)
    input_dir = project_dir / "input"
    output_dir = project_dir / "output"
    logs_dir = project_dir / "logs"
    analysis_dir = project_dir / "analysis"
    report_dir = project_dir / "report"

    for d in (output_dir, logs_dir, analysis_dir, report_dir):
        d.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / f"{job.id}.log"
    _log(log_file, f"BindCraft Job {job.id} | Mode: {mode} | {datetime.utcnow().isoformat()}")

    # Load settings
    if not project.settings_json:
        return False, "Project settings not configured. Please complete the Setup Wizard."

    ps = ProjectSettings.model_validate_json(project.settings_json)
    ligand_name = project.ligand_name or "LIG"

    # Determine PDB stem
    pdb_path = (input_dir / project.pdb_filename) if project.pdb_filename else None
    if not pdb_path or not pdb_path.exists():
        return False, "PDB file not found. Please re-upload your complex."

    pdb_stem = pdb_path.stem

    # ── Step 0: Render templates ─────────────────────────────────────────────
    _update_step(job, db, "Rendering AMBER input files")
    try:
        rendered = template_engine.render_all_templates(ps, ligand_name, pdb_stem)
    except Exception as exc:
        return False, f"Template rendering failed: {exc}"

    # Save rendered files to input dir (for download/review)
    for fname, content in rendered.items():
        (input_dir / fname).write_text(content, encoding="utf-8")
        _log(log_file, f"[OK] Rendered {fname}")

    if mode == "generate":
        _log(log_file, "[OK] Generate-only mode: all input files created.")
        _build_report(project, ps, rendered, report_dir, log_file)
        return True, None

    # ── Mode: run — requires WSL ─────────────────────────────────────────────
    if not wsl_runner.is_wsl_available():
        return False, (
            "WSL2 not detected. Run mode requires WSL2 with Ubuntu and AmberTools installed. "
            "See README for setup instructions. Use 'Generate Only' to download input files "
            "and run them manually."
        )

    # ── Step 1: pdb4amber ────────────────────────────────────────────────────
    _update_step(job, db, "Cleaning PDB with pdb4amber")
    clean_pdb = input_dir / f"{pdb_stem}_clean.pdb"
    r = wsl_runner.run_in_wsl(
        "pdb4amber",
        [
            "-i", wsl_runner.win_to_wsl_path(pdb_path),
            "-o", wsl_runner.win_to_wsl_path(clean_pdb),
            "--nohyd",  # remove existing H, tleap will add them
        ],
        cwd_win=input_dir,
        log_file=log_file,
    )
    if r.returncode != 0:
        return False, _parse_error(log_file, "pdb4amber failed. The PDB file may have formatting issues.")

    # ── Step 2: antechamber ──────────────────────────────────────────────────
    lig_input = _find_ligand_file(input_dir, project)
    if lig_input:
        fmt = "mdl" if lig_input.suffix.lower() == ".sdf" else "mol2"
    else:
        # Extract ligand from PDB
        lig_input = clean_pdb
        fmt = "pdb"

    _update_step(job, db, "Parameterising ligand with antechamber (GAFF2)")
    lig_mol2 = input_dir / f"{ligand_name}_gaff2.mol2"
    r = wsl_runner.run_in_wsl(
        "antechamber",
        [
            "-i", wsl_runner.win_to_wsl_path(lig_input),
            "-fi", fmt,
            "-o", wsl_runner.win_to_wsl_path(lig_mol2),
            "-fo", "mol2",
            "-c", "bcc",              # AM1-BCC charges
            "-nc", str(project.ligand_charge or 0),
            "-s", "2",
            "-at", "gaff2",
            "-rn", ligand_name[:3].upper(),
            "-pf", "y",
        ],
        cwd_win=input_dir,
        log_file=log_file,
    )
    if r.returncode != 0:
        return False, _parse_error(
            log_file,
            "Ligand parameterisation (antechamber) failed. "
            "Check the net charge and ensure no unusual elements are present.",
        )

    # ── Step 3: parmchk2 ─────────────────────────────────────────────────────
    _update_step(job, db, "Generating missing parameters with parmchk2")
    frcmod = input_dir / f"{ligand_name}.frcmod"
    r = wsl_runner.run_in_wsl(
        "parmchk2",
        [
            "-i", wsl_runner.win_to_wsl_path(lig_mol2),
            "-f", "mol2",
            "-o", wsl_runner.win_to_wsl_path(frcmod),
            "-s", "gaff2",
        ],
        cwd_win=input_dir,
        log_file=log_file,
    )
    if r.returncode != 0:
        return False, _parse_error(log_file, "parmchk2 failed. See the log for missing parameters.")

    # ── Step 4: tleap ─────────────────────────────────────────────────────────
    _update_step(job, db, "Building topology with tleap")
    tleap_in = input_dir / "tleap.in"
    r = wsl_runner.run_in_wsl(
        "tleap",
        ["-f", wsl_runner.win_to_wsl_path(tleap_in)],
        cwd_win=input_dir,
        log_file=log_file,
    )
    if r.returncode != 0:
        return False, _parse_error(
            log_file,
            "System building (tleap) failed. Common causes: non-standard residues, "
            "missing parameters, or incorrect ligand name.",
        )

    # Expect prmtop + inpcrd to exist after tleap
    prmtop = input_dir / "complex.prmtop"
    inpcrd = input_dir / "complex.inpcrd"
    if not prmtop.exists() or not inpcrd.exists():
        return False, "tleap did not create expected output files (complex.prmtop / complex.inpcrd)."

    # ── Steps 5a–5d: sander ──────────────────────────────────────────────────
    stages = [
        ("Minimization", "min"),
        ("Heating (NVT)", "heat"),
        ("Equilibration (NPT)", "equil"),
        ("Production (NPT)", "prod"),
    ]
    prev_rst = inpcrd
    for label, stage in stages:
        _update_step(job, db, f"sander: {label}")
        mdin = input_dir / f"{stage}.mdin"
        mdout = output_dir / f"{stage}.mdout"
        rst7 = output_dir / f"{stage}.rst7"
        mdcrd = output_dir / f"{stage}.mdcrd"

        r = wsl_runner.run_in_wsl(
            "sander",
            [
                "-O",
                "-i", wsl_runner.win_to_wsl_path(mdin),
                "-o", wsl_runner.win_to_wsl_path(mdout),
                "-p", wsl_runner.win_to_wsl_path(prmtop),
                "-c", wsl_runner.win_to_wsl_path(prev_rst),
                "-r", wsl_runner.win_to_wsl_path(rst7),
                "-x", wsl_runner.win_to_wsl_path(mdcrd),
            ],
            cwd_win=output_dir,
            log_file=log_file,
        )
        if r.returncode != 0:
            return False, _parse_error(
                log_file,
                f"sander failed during {label}. "
                "This could indicate memory issues or bad initial structure.",
            )
        prev_rst = rst7

    # ── Step 6: cpptraj ──────────────────────────────────────────────────────
    _update_step(job, db, "Running cpptraj analysis")
    cpptraj_in = input_dir / "cpptraj.in"
    r = wsl_runner.run_in_wsl(
        "cpptraj",
        [
            "-p", wsl_runner.win_to_wsl_path(prmtop),
            "-i", wsl_runner.win_to_wsl_path(cpptraj_in),
        ],
        cwd_win=analysis_dir,
        log_file=log_file,
    )
    if r.returncode != 0:
        # Non-fatal — still return success with warning
        _log(log_file, "[WARNING] cpptraj analysis failed. Charts will not be available.")
    else:
        _log(log_file, "[OK] cpptraj analysis complete.")

    # Build reproducibility report
    _build_report(project, ps, rendered, report_dir, log_file)

    _log(log_file, "\n[SUCCESS] BindCraft pipeline complete!")
    return True, None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _update_step(job: Job, db: Session, step: str) -> None:
    job.current_step = step
    db.commit()
    logger.info("Job %s: %s", job.id, step)


def _log(log_file: Path, msg: str) -> None:
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}\n")
    logger.info(msg)


def _find_ligand_file(input_dir: Path, project: Project) -> Path | None:
    if project.ligand_filename:
        p = input_dir / project.ligand_filename
        if p.exists():
            return p
    return None


def _parse_error(log_file: Path, default_msg: str) -> str:
    """Look for known error patterns in the log and return a friendly message."""
    try:
        content = log_file.read_text(errors="replace")
        for pattern, msg in _ERROR_MAP:
            if pattern.lower() in content.lower():
                return msg
    except Exception:
        pass
    return default_msg


def _build_report(project, ps, rendered, report_dir, log_file):
    """Build a simple HTML reproducibility report."""
    from backend.services.report_builder import build_report
    try:
        build_report(project, ps, rendered, report_dir)
    except Exception as exc:
        _log(log_file, f"[WARNING] Report generation failed: {exc}")
