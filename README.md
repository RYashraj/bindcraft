# BindCraft 🔬

**A beginner-friendly, no-code AMBER molecular dynamics platform for pharmacy students.**

BindCraft guides B.Pharm and M.Pharm students through the process of setting up, running, and analysing protein–ligand molecular dynamics simulations without needing to learn Linux commands or complex AMBER syntax.

## Features
- **No-code Pipeline:** Upload a PDB and ligand, pick simple settings, and run.
- **Educational Guardrails:** Validates inputs, locks complex force fields to best-practice defaults (ff14SB + GAFF2), and provides plain-English error messages.
- **Three Modes:**
  - **Demo Mode:** Explore a realistic AChE + Donepezil simulation instantly.
  - **Generate Only:** Create and download the AMBER input files on any Windows PC.
  - **Run Local:** Execute the full simulation using WSL2 and free AmberTools.
- **Live Analysis:** Visualise Potential Energy, Temperature, RMSD, RMSF, and Radius of Gyration using Plotly.
- **Offline First:** Runs entirely on localhost. No cloud, no accounts, no subscriptions.

> ⚠️ **Educational Disclaimer:** BindCraft does *not* perform molecular docking. The ligand must already be positioned in its binding site. Results are for educational purposes and should not be used for clinical validation or publication without expert review.

---

## Installation (Windows)

BindCraft is designed to run locally on Windows 10/11.

### 1. Requirements
- Python 3.10+
- (Optional but recommended) WSL2 with Ubuntu
- (Optional but recommended) AmberTools installed inside WSL2

### 2. Setup
Clone the repository and run the launcher:
```bash
git clone https://github.com/RYashraj/bindcraft.git
cd bindcraft
```
Double-click `start.bat`. This will:
1. Create a Python virtual environment.
2. Install dependencies.
3. Start the FastAPI server on `http://localhost:8000`.
4. Open your default web browser.

### 3. AmberTools Setup (for Run Mode)
To actually *run* simulations, you need AmberTools inside WSL2.
1. Install WSL2: Open PowerShell as Admin and run `wsl --install`. Restart PC.
2. Open Ubuntu.
3. Install Miniconda in Ubuntu:
   ```bash
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
   bash Miniconda3-latest-Linux-x86_64.sh
   ```
4. Install AmberTools (Free):
   ```bash
   conda create -n ambertools ambertools -c conda-forge
   ```
5. Edit the `.env` file in the BindCraft folder if your AmberTools path differs from the default.

---

## Architecture

- **Backend:** Python FastAPI, SQLAlchemy (SQLite), Pydantic.
- **Frontend:** Vanilla HTML/CSS/JS (SPA), Plotly.js for charts.
- **Pipeline:** Orchestrates `pdb4amber` → `antechamber` → `parmchk2` → `tleap` → `sander` → `cpptraj`.
- **Database:** Local SQLite (`projects/bindcraft.db`).

## License
Open Source. Uses free tools only.
