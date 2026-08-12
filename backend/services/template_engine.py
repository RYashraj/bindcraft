"""
Template engine — render AMBER input files from editable templates.

Templates live in backend/templates/ and use {{PLACEHOLDER}} syntax.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.config import settings
from backend.schemas import ProjectSettings

# Preset definitions
PRESETS: dict[str, dict] = {
    "fast_test": {
        "label": "Fast Learning Test",
        "min_steps": 2000,
        "heat_ns": 0.01,   # 10 ps
        "equil_ns": 0.02,  # 20 ps
        "prod_ns": 0.05,   # 50 ps
        "description": "Minimization + 10 ps heating + 20 ps equilibration + 50 ps production",
    },
    "basic_test": {
        "label": "Basic Test",
        "min_steps": 5000,
        "heat_ns": 0.02,   # 20 ps
        "equil_ns": 0.10,  # 100 ps
        "prod_ns": 0.10,   # 100 ps
        "description": "Minimization + 20 ps heating + 100 ps equilibration + 100 ps production",
    },
}

# 1 ps = 500 steps with dt=0.002 ps
_STEPS_PER_NS = 500_000  # dt = 0.002 ps


def ns_to_steps(ns: float) -> int:
    return int(ns * _STEPS_PER_NS)


def render_all_templates(
    project_settings: ProjectSettings,
    ligand_name: str,
    pdb_stem: str,
) -> dict[str, str]:
    """
    Render all AMBER input templates and return dict of {filename: content}.
    """
    preset = PRESETS[project_settings.preset]
    ctx = _build_context(project_settings, preset, ligand_name, pdb_stem)

    results: dict[str, str] = {}

    # Which tleap template to use
    tleap_tmpl = (
        "tleap_explicit.in"
        if project_settings.solvent_type == "explicit"
        else "tleap_implicit.in"
    )
    results["tleap.in"] = _render(tleap_tmpl, ctx)
    results["min.mdin"] = _render("min.mdin", ctx)
    results["heat.mdin"] = _render("heat.mdin", ctx)
    results["equil.mdin"] = _render("equil.mdin", ctx)
    results["prod.mdin"] = _render("prod.mdin", ctx)
    results["cpptraj.in"] = _render("cpptraj.in", ctx)

    return results


def _build_context(
    ps: ProjectSettings,
    preset: dict,
    ligand_name: str,
    pdb_stem: str,
) -> dict:
    return {
        "LIGAND_NAME": ligand_name.upper()[:3],
        "PROTEIN_FF": ps.protein_ff,
        "LIGAND_FF": ps.ligand_ff.lower(),  # gaff2
        "WATER_MODEL": ps.water_model.lower(),  # tip3p
        "BOX_PADDING": str(ps.box_padding),
        "TEMP": str(ps.temperature),
        "PRESSURE": str(ps.pressure),
        "MIN_STEPS": str(preset["min_steps"]),
        "HEAT_NSTLIM": str(ns_to_steps(preset["heat_ns"])),
        "EQUIL_NSTLIM": str(ns_to_steps(preset["equil_ns"])),
        "PROD_NSTLIM": str(ns_to_steps(preset["prod_ns"])),
        "OUTPUT_FREQ": str(ps.output_freq),
        "PDB_STEM": pdb_stem,
        "PRESET_LABEL": preset["label"],
        "PRESET_DESC": preset["description"],
    }


def _render(template_name: str, context: dict) -> str:
    tmpl_path = settings.templates_dir / template_name
    if not tmpl_path.exists():
        raise FileNotFoundError(f"Template not found: {tmpl_path}")
    content = tmpl_path.read_text(encoding="utf-8")
    for key, value in context.items():
        content = content.replace("{{" + key + "}}", value)
    # Warn about unreplaced placeholders
    unreplaced = re.findall(r"\{\{(\w+)\}\}", content)
    if unreplaced:
        import logging
        logging.getLogger("bindcraft.templates").warning(
            "Unreplaced placeholders in %s: %s", template_name, unreplaced
        )
    return content


def get_preset_info(preset_key: str) -> dict:
    return PRESETS.get(preset_key, PRESETS["fast_test"])
