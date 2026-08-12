"""
WSL Runner — safe subprocess wrapper for AmberTools inside WSL2.

Security rules:
- Never uses shell=True.
- All arguments are passed as a list.
- User-provided filenames are sanitised and confined to project directories.
- Windows paths are translated to WSL paths automatically.
"""
from __future__ import annotations

import logging
import platform
import re
import subprocess
from pathlib import Path, PurePosixPath

from backend.config import settings

logger = logging.getLogger("bindcraft.wsl")

_SAFE_FILENAME_RE = re.compile(r"^[\w\-. ()]+$")


def is_wsl_available() -> bool:
    if platform.system() != "Windows":
        return True  # On Linux dev machines, run natively
    try:
        r = subprocess.run(
            ["wsl", "--list", "--quiet"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def win_to_wsl_path(win_path: Path) -> str:
    """Convert a Windows path like C:\\foo\\bar to /mnt/c/foo/bar."""
    if platform.system() != "Windows":
        return str(win_path)
    resolved = win_path.resolve()
    drive = resolved.drive  # e.g. "C:"
    rest = str(resolved)[len(drive):].replace("\\", "/")
    drive_letter = drive.rstrip(":").lower()
    return f"/mnt/{drive_letter}{rest}"


def sanitise_filename(filename: str) -> str:
    """Raise ValueError if the filename looks dangerous."""
    if not _SAFE_FILENAME_RE.match(filename):
        raise ValueError(f"Unsafe filename: {filename!r}")
    return filename


def run_in_wsl(
    tool: str,
    args: list[str],
    cwd_win: Path,
    log_file: Path,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """
    Run an AmberTools executable inside WSL2.

    Parameters
    ----------
    tool      : AmberTools executable name (e.g. "antechamber")
    args      : Additional arguments as a list (NOT a shell string)
    cwd_win   : Working directory (Windows path; converted to WSL path)
    log_file  : Where to append stdout+stderr
    env_extra : Additional environment variables for the WSL session
    """
    tool_path = settings.tool_path(tool)
    cwd_wsl = win_to_wsl_path(cwd_win)

    if platform.system() == "Windows":
        cmd = ["wsl", "-d", settings.wsl_distro, "--", "bash", "-lc",
               f"cd {cwd_wsl} && {tool_path} " + " ".join(
                   _quote_wsl(a) for a in args
               )]
    else:
        # Linux/Mac dev — run tool directly
        cmd = [tool_path] + args

    logger.info("Running: %s", " ".join(cmd))

    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n{'='*60}\n$ {' '.join(cmd)}\n{'='*60}\n")
        result = subprocess.run(
            cmd,
            cwd=str(cwd_win),
            stdout=lf,
            stderr=subprocess.STDOUT,
            timeout=3600,  # 1-hour timeout
        )
        lf.write(f"\n[Return code: {result.returncode}]\n")

    return result


def run_native(
    cmd: list[str],
    cwd: Path,
    log_file: Path,
) -> subprocess.CompletedProcess:
    """Run a command natively on Windows (no WSL). Used for non-AMBER tasks."""
    logger.info("Native run: %s", " ".join(cmd))
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n$ {' '.join(cmd)}\n")
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=lf,
            stderr=subprocess.STDOUT,
            timeout=600,
        )
        lf.write(f"\n[Return code: {result.returncode}]\n")
    return result


def _quote_wsl(arg: str) -> str:
    """Wrap an argument in single quotes for bash -lc."""
    return "'" + arg.replace("'", "'\\''") + "'"
