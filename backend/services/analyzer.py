"""
Analyzer service — parse mdout files and cpptraj CSVs into chart data.
"""
from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from backend.schemas import ChartData

logger = logging.getLogger("bindcraft.analyzer")


def load_chart_data(project_dir: Path) -> ChartData:
    """Load all available chart data for a project."""
    output_dir = project_dir / "output"
    analysis_dir = project_dir / "analysis"

    energy, temperature = _parse_mdout_files(output_dir)
    rmsd = _parse_csv(analysis_dir / "rmsd.csv", "RMSD (Å)")
    rmsf = _parse_csv(analysis_dir / "rmsf.csv", "RMSF (Å)")
    rg = _parse_csv(analysis_dir / "rg.csv", "Rg (Å)")

    return ChartData(
        energy=energy,
        temperature=temperature,
        rmsd=rmsd,
        rmsf=rmsf,
        rg=rg,
    )


def _parse_mdout_files(output_dir: Path) -> tuple[list[dict], list[dict]]:
    """Parse all stage mdout files for EPTOT and TEMP."""
    energy_points: list[dict] = []
    temp_points: list[dict] = []
    step_offset = 0

    for stage in ("min", "heat", "equil", "prod"):
        mdout = output_dir / f"{stage}.mdout"
        if not mdout.exists():
            continue
        eng, tmp = _parse_single_mdout(mdout, step_offset, stage)
        energy_points.extend(eng)
        temp_points.extend(tmp)
        if eng:
            step_offset = eng[-1]["x"] + 1

    return energy_points, temp_points


def _parse_single_mdout(path: Path, step_offset: int, stage: str) -> tuple[list[dict], list[dict]]:
    """
    Parse an AMBER mdout file.
    Returns (energy_series, temperature_series) as lists of {x, y, stage} dicts.
    """
    energy_series: list[dict] = []
    temp_series: list[dict] = []

    content = path.read_text(errors="replace")

    # AMBER mdout records look like:
    #  NSTEP =      500   TIME(PS) =       1.000  TEMP(K) =   299.93  PRESS =     0.0
    #  Etot   =    -12345.6789  EKtot   =     2345.6789  EPtot      =    -14691.3578
    nstep_re = re.compile(
        r"NSTEP\s*=\s*(\d+)\s+TIME\(PS\)\s*=\s*([\d.]+)\s+TEMP\(K\)\s*=\s*([\d.]+)",
        re.MULTILINE,
    )
    eptot_re = re.compile(r"EPtot\s*=\s*([-\d.]+)", re.MULTILINE)

    nstep_matches = list(nstep_re.finditer(content))
    eptot_matches = list(eptot_re.finditer(content))

    for i, m in enumerate(nstep_matches):
        nstep = int(m.group(1)) + step_offset
        temp = float(m.group(3))
        temp_series.append({"x": nstep, "y": temp, "stage": stage})

        if i < len(eptot_matches):
            eptot = float(eptot_matches[i].group(1))
            energy_series.append({"x": nstep, "y": eptot, "stage": stage})

    return energy_series, temp_series


def _parse_csv(path: Path, y_label: str) -> list[dict]:
    """Parse a cpptraj-generated CSV file."""
    if not path.exists():
        return []

    results: list[dict] = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            # cpptraj CSVs can have # comment headers
            lines = [l for l in f if not l.startswith("#")]

        reader = csv.reader(lines)
        headers = None
        for row in reader:
            if not row:
                continue
            if headers is None:
                headers = row
                continue
            if len(row) >= 2:
                try:
                    results.append({
                        "x": float(row[0]),
                        "y": float(row[1]),
                    })
                except ValueError:
                    pass
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)

    return results
