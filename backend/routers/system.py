"""
System check router — detect WSL2, AmberTools, disk space.
"""
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

from backend.config import settings
from backend.schemas import SystemCheck

router = APIRouter()


@router.get("/check", response_model=SystemCheck)
def system_check():
    wsl_ok, distro = _check_wsl()
    amber_ok, tools = _check_ambertools() if wsl_ok else (False, {})
    disk = _disk_free_gb()

    return SystemCheck(
        wsl_available=wsl_ok,
        wsl_distro=distro,
        ambertools_available=amber_ok,
        tools=tools,
        disk_free_gb=disk,
        python_version=sys.version,
    )


def _check_wsl() -> tuple[bool, str | None]:
    """Return (available, distro_name)."""
    if platform.system() != "Windows":
        # On Linux/Mac (e.g. dev machine), assume available
        return True, "native"
    try:
        result = subprocess.run(
            ["wsl", "--list", "--quiet"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [l.strip().strip("\x00") for l in result.stdout.splitlines() if l.strip()]
        distro = settings.wsl_distro
        if lines:
            return True, distro
        return False, None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, None


def _check_ambertools() -> tuple[bool, dict[str, bool]]:
    """Check each AmberTools executable via WSL."""
    tools_to_check = [
        settings.pdb4amber_exe,
        settings.antechamber_exe,
        settings.parmchk2_exe,
        settings.tleap_exe,
        settings.sander_exe,
        settings.cpptraj_exe,
    ]
    results: dict[str, bool] = {}

    for tool in tools_to_check:
        tool_path = settings.tool_path(tool)
        try:
            r = subprocess.run(
                ["wsl", "-d", settings.wsl_distro, "--", "test", "-x", tool_path],
                capture_output=True,
                timeout=5,
            )
            results[tool] = r.returncode == 0
        except Exception:
            results[tool] = False

    all_ok = all(results.values())
    return all_ok, results


def _disk_free_gb() -> float:
    try:
        usage = shutil.disk_usage(str(settings.projects_dir.parent))
        return round(usage.free / (1024**3), 2)
    except Exception:
        return -1.0
