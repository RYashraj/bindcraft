"""
Validator service — checks uploaded PDB, SDF, and MOL2 files.

Validation philosophy:
- Errors (level="error") block proceeding.
- Warnings (level="warning") require user acknowledgement.
- Info (level="info") are purely educational notes.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.schemas import ValidationResult, ValidationWarning

# Residue names that GAFF2 / tleap cannot handle without special treatment
_UNSUPPORTED_RESIDUES = frozenset(
    ["MSE", "SEP", "TPO", "PTR", "CSO", "HIC", "MLZ", "OCS"]
)

# Standard amino acids (20 + common variants with H)
_STD_RESIDUES = frozenset([
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS",
    "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP",
    "TYR", "VAL", "HIE", "HID", "HIP", "CYX",
])

# Water and common ions
_SOLVENT_RESIDUES = frozenset(["HOH", "WAT", "NA", "CL", "MG", "CA", "ZN", "FE"])


def validate_project_files(
    pdb_path: Path | None,
    ligand_path: Path | None,
    charge: int = 0,
) -> ValidationResult:
    warnings: list[ValidationWarning] = []
    valid = True

    # ─── Must have a PDB ─────────────────────────────────────────────────────
    if not pdb_path or not pdb_path.exists():
        warnings.append(ValidationWarning(
            level="error",
            code="NO_PDB",
            message="No complex PDB file provided.",
            detail=(
                "Please upload a PDB file containing both the protein and the "
                "ligand in its binding pose. BindCraft does not perform docking — "
                "the ligand must already be placed correctly."
            ),
        ))
        return ValidationResult(valid=False, warnings=warnings)

    # ─── Parse PDB ───────────────────────────────────────────────────────────
    lines = pdb_path.read_text(errors="replace").splitlines()
    atom_lines = [l for l in lines if l.startswith(("ATOM  ", "HETATM"))]
    hetatm_lines = [l for l in lines if l.startswith("HETATM")]

    if not atom_lines:
        warnings.append(ValidationWarning(
            level="error",
            code="NO_ATOMS",
            message="The PDB file contains no ATOM or HETATM records.",
            detail="Ensure the file is a valid PDB with coordinate data.",
        ))
        valid = False

    atom_count = len(atom_lines)
    residue_count = _count_residues(atom_lines)

    # ─── Detect ligand residue ────────────────────────────────────────────────
    ligand_residue = _detect_ligand_residue(hetatm_lines)

    if not hetatm_lines:
        warnings.append(ValidationWarning(
            level="error",
            code="NO_LIGAND_IN_PDB",
            message="No HETATM records found in the PDB file.",
            detail=(
                "BindCraft requires the ligand to already be positioned in the "
                "binding site (as HETATM records). Please prepare your complex "
                "using a docking tool (e.g., AutoDock Vina) or take a co-crystal "
                "structure from PDB, then upload the complex."
            ),
        ))
        valid = False
    else:
        warnings.append(ValidationWarning(
            level="info",
            code="LIGAND_DETECTED",
            message=f"Ligand residue detected: {ligand_residue}",
            detail=(
                "BindCraft found a non-standard residue in the HETATM records. "
                "It will be parameterised with GAFF2 + antechamber."
            ),
        ))

    # ─── Hydrogens ───────────────────────────────────────────────────────────
    has_h = _has_hydrogens(atom_lines)
    if not has_h:
        warnings.append(ValidationWarning(
            level="warning",
            code="NO_HYDROGENS",
            message="No hydrogen atoms detected in the PDB file.",
            detail=(
                "pdb4amber will attempt to add hydrogens automatically. "
                "For best results, pre-protonate the structure with a tool like "
                "H++ or PropKa before uploading."
            ),
        ))

    # ─── Unsupported residues ─────────────────────────────────────────────────
    non_std = _find_non_standard(atom_lines)
    if non_std:
        warnings.append(ValidationWarning(
            level="warning",
            code="NON_STANDARD_RESIDUES",
            message=f"Non-standard residues found: {', '.join(sorted(non_std))}",
            detail=(
                "These residues may require special parameters. "
                "tleap may fail if they are not supported by ff14SB."
            ),
        ))

    # ─── Size warning ─────────────────────────────────────────────────────────
    if atom_count > 30000:
        warnings.append(ValidationWarning(
            level="warning",
            code="LARGE_SYSTEM",
            message=f"Large system: {atom_count} atoms detected.",
            detail=(
                "Simulations with >30,000 atoms may take a long time on CPU-only sander. "
                "Consider using a smaller system or a subset for initial learning."
            ),
        ))

    # ─── Ligand file ─────────────────────────────────────────────────────────
    if not ligand_path or not ligand_path.exists():
        warnings.append(ValidationWarning(
            level="warning",
            code="NO_LIGAND_FILE",
            message="No separate ligand SDF/MOL2 file provided.",
            detail=(
                "antechamber will attempt to extract the ligand directly from the PDB. "
                "Providing a separate SDF or MOL2 file gives better results for "
                "charge assignment."
            ),
        ))
    else:
        ext = ligand_path.suffix.lower()
        if ext not in (".sdf", ".mol2"):
            warnings.append(ValidationWarning(
                level="error",
                code="UNSUPPORTED_LIGAND_FORMAT",
                message=f"Ligand file format '{ext}' is not supported.",
                detail="Please provide the ligand as SDF (.sdf) or MOL2 (.mol2).",
            ))
            valid = False
        else:
            lig_ok, lig_warn = _validate_ligand_file(ligand_path, ext)
            warnings.extend(lig_warn)
            if not lig_ok:
                valid = False

    # ─── Charge ──────────────────────────────────────────────────────────────
    if abs(charge) > 4:
        warnings.append(ValidationWarning(
            level="warning",
            code="HIGH_CHARGE",
            message=f"Ligand net charge of {charge} is unusually high.",
            detail=(
                "Most drug-like ligands have a net charge between -2 and +2. "
                "Please double-check the charge before proceeding."
            ),
        ))

    return ValidationResult(
        valid=valid,
        warnings=warnings,
        residue_count=residue_count,
        atom_count=atom_count,
        ligand_residue=ligand_residue,
        has_hydrogens=has_h,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _count_residues(atom_lines: list[str]) -> int:
    seen: set[tuple] = set()
    for line in atom_lines:
        try:
            chain = line[21]
            res_seq = line[22:26].strip()
            seen.add((chain, res_seq))
        except IndexError:
            pass
    return len(seen)


def _detect_ligand_residue(hetatm_lines: list[str]) -> str | None:
    for line in hetatm_lines:
        try:
            res_name = line[17:20].strip()
            if res_name and res_name not in _SOLVENT_RESIDUES:
                return res_name
        except IndexError:
            pass
    return None


def _has_hydrogens(atom_lines: list[str]) -> bool:
    for line in atom_lines:
        try:
            # Element column (77-78) or name column (12-16)
            element = line[76:78].strip() if len(line) >= 78 else ""
            name = line[12:16].strip()
            if element == "H" or name.startswith("H"):
                return True
        except IndexError:
            pass
    return False


def _find_non_standard(atom_lines: list[str]) -> set[str]:
    found: set[str] = set()
    for line in atom_lines:
        try:
            res = line[17:20].strip()
            if res and res not in _STD_RESIDUES and res not in _SOLVENT_RESIDUES:
                if line.startswith("ATOM  "):  # HETATM is expected non-std
                    found.add(res)
        except IndexError:
            pass
    return found & _UNSUPPORTED_RESIDUES


def _validate_ligand_file(path: Path, ext: str) -> tuple[bool, list[ValidationWarning]]:
    warnings: list[ValidationWarning] = []
    content = path.read_text(errors="replace")

    if ext == ".sdf":
        if "$$$$" not in content:
            warnings.append(ValidationWarning(
                level="warning",
                code="SDF_NO_TERMINATOR",
                message="SDF file missing '$$$$' terminator.",
                detail="The SDF file may be malformed.",
            ))
        # Check molecule block exists
        lines = content.splitlines()
        if len(lines) < 4:
            warnings.append(ValidationWarning(
                level="error",
                code="SDF_TOO_SHORT",
                message="SDF file appears to be empty or too short.",
                detail="Provide a valid SDF file from a structure tool like Marvin or RDKit.",
            ))
            return False, warnings

    elif ext == ".mol2":
        if "@<TRIPOS>MOLECULE" not in content:
            warnings.append(ValidationWarning(
                level="error",
                code="MOL2_INVALID",
                message="MOL2 file missing @<TRIPOS>MOLECULE section.",
                detail="The file does not appear to be a valid Tripos MOL2.",
            ))
            return False, warnings

    return True, warnings
