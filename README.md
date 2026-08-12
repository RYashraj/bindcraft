# BindCraft

> Molecular Dynamics for Medicine.

BindCraft is a beginner-friendly local application that helps pharmacy students set up, run, and analyse short protein–ligand molecular dynamics (MD) simulations using AMBER—without writing AMBER command files manually.

## What it does

- Upload a protein structure (`.pdb`) and ligand (`.sdf` or `.mol2`)
- Select simple simulation settings through a guided interface
- Generate AMBER input files automatically
- Run short local MD simulations through WSL2
- View energy, temperature, RMSD, RMSF, and radius-of-gyration plots
- Download all generated files, logs, results, and a reproducibility report

## Who is it for?

B.Pharm and life-science students who want to learn molecular dynamics and protein–ligand simulation workflows without needing prior programming experience.

## Workflow

```text
Upload Protein + Ligand
        ↓
Choose Simulation Settings
        ↓
Prepare System with AMBER Tools
        ↓
Minimization → Heating → Equilibration → Production MD
        ↓
Analyse Results and Download Report
