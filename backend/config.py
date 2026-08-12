"""
BindCraft Configuration
Reads from .env file; falls back to sensible defaults.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # WSL / AmberTools
    wsl_distro: str = "Ubuntu"
    ambertools_bin: str = "/usr/local/miniconda3/envs/ambertools/bin"

    # Storage
    projects_dir: Path = Path("./projects")
    demo_dir: Path = Path("./demo")

    # Templates
    templates_dir: Path = Path("./backend/templates")

    # App
    log_level: str = "INFO"
    app_name: str = "BindCraft"
    version: str = "1.0.0"

    # AmberTools executables (relative to ambertools_bin)
    pdb4amber_exe: str = "pdb4amber"
    antechamber_exe: str = "antechamber"
    parmchk2_exe: str = "parmchk2"
    tleap_exe: str = "tleap"
    sander_exe: str = "sander"
    cpptraj_exe: str = "cpptraj"

    def tool_path(self, tool: str) -> str:
        """Return the full path to an AmberTools executable inside WSL."""
        return f"{self.ambertools_bin}/{tool}"

    def project_path(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def ensure_dirs(self) -> None:
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.demo_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
