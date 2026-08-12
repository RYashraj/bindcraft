"""BindCraft Desktop GUI entry point.

This native GUI uses Tkinter and talks to the existing FastAPI backend
over HTTP. If the backend is not running on localhost:8000 the GUI will
start it in a background thread.

The GUI is intentionally simple: dashboard, create project, upload files,
start jobs (generate/run/demo) and view logs. It's a lightweight native
front-end alternative to the web UI used during development.
"""
from __future__ import annotations

import threading
import time
import socket
import logging
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

import httpx

import uvicorn

API_URL = "http://127.0.0.1:8000"
LOG = logging.getLogger("bindcraft.gui")


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_server():
    """Start the FastAPI backend using uvicorn."""
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, log_level="info")


class BindCraftGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("BindCraft — Desktop")
        root.geometry("1000x700")

        self.client = httpx.Client(timeout=10.0)

        # Top controls
        top = ttk.Frame(root)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        ttk.Button(top, text="Refresh Projects", command=self.refresh_projects).pack(side=tk.LEFT)
        ttk.Button(top, text="New Project", command=self.create_project_dialog).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Upload Files", command=self.upload_files_dialog).pack(side=tk.LEFT)
        ttk.Button(top, text="Start Generate", command=lambda: self.start_job("generate")).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Start Run", command=lambda: self.start_job("run")).pack(side=tk.LEFT)
        ttk.Button(top, text="Demo Mode", command=lambda: self.start_job("demo")).pack(side=tk.LEFT, padx=8)

        # Main paned view
        paned = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Left: project list
        left = ttk.Frame(paned, width=300)
        paned.add(left, weight=1)
        ttk.Label(left, text="Projects").pack(anchor=tk.W)
        self.project_list = tk.Listbox(left)
        self.project_list.pack(fill=tk.BOTH, expand=True)
        self.project_list.bind("<<ListboxSelect>>", self.on_project_select)

        # Right: details and logs
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        ttk.Label(right, text="Project Details / Logs").pack(anchor=tk.W)
        self.details = tk.Text(right, height=15)
        self.details.pack(fill=tk.BOTH, expand=False)

        ttk.Label(right, text="Job Logs").pack(anchor=tk.W, pady=(8, 0))
        self.logs = tk.Text(right)
        self.logs.pack(fill=tk.BOTH, expand=True)

        self.projects = []
        self.selected_project = None

        self.refresh_projects()

    def api(self, method: str, path: str, **kwargs):
        url = API_URL + path
        try:
            r = self.client.request(method, url, **kwargs)
            r.raise_for_status()
            return r
        except Exception as exc:
            LOG.exception("API error %s %s", method, path)
            messagebox.showerror("API error", f"Error calling {path}: {exc}")
            return None

    def refresh_projects(self):
        self.project_list.delete(0, tk.END)
        r = self.api("GET", "/api/projects/")
        if not r:
            return
        self.projects = r.json()
        for p in self.projects:
            display = f"{p['name']} — {p['status']} ({p['id'][:8]})"
            self.project_list.insert(tk.END, display)

    def on_project_select(self, _evt=None):
        sel = self.project_list.curselection()
        if not sel:
            return
        idx = sel[0]
        project = self.projects[idx]
        self.selected_project = project
        # show details
        self.details.delete("1.0", tk.END)
        for k in ("id", "name", "notes", "status", "pdb_filename", "ligand_filename", "ligand_charge"):
            self.details.insert(tk.END, f"{k}: {project.get(k)}\n")

        # fetch jobs and show most recent logs if any
        r = self.api("GET", f"/api/jobs/?project_id={project['id']}")
        self.logs.delete("1.0", tk.END)
        if not r:
            return
        jobs = r.json()
        if not jobs:
            self.logs.insert(tk.END, "No jobs for this project.\n")
            return
        latest = jobs[0]
        self.logs.insert(tk.END, f"Latest job: {latest['id']} — {latest['status']}\n")
        r2 = self.api("GET", f"/api/jobs/{latest['id']}/logs")
        if r2:
            logtxt = r2.json().get("log") if r2.headers.get("content-type", "").startswith("application/json") else r2.text
            if isinstance(logtxt, dict):
                logtxt = logtxt.get("log", "")
            self.logs.insert(tk.END, logtxt)

    def create_project_dialog(self):
        name = simpledialog.askstring("Project name", "Enter project name:")
        if not name:
            return
        notes = simpledialog.askstring("Notes", "Optional notes:")
        r = self.api("POST", "/api/projects/", json={"name": name, "notes": notes})
        if r:
            messagebox.showinfo("Project created", f"Project '{name}' created")
            self.refresh_projects()

    def upload_files_dialog(self):
        if not self.selected_project:
            messagebox.showwarning("Select project", "Please select a project first.")
            return
        pdb_file = filedialog.askopenfilename(title="Select complex PDB", filetypes=[("PDB files", "*.pdb")])
        lig_file = filedialog.askopenfilename(title="Select ligand SDF/MOL2 (optional)", filetypes=[("SDF/MOL2", "*.sdf;*.mol2")])
        charge = simpledialog.askinteger("Ligand net charge", "Enter ligand net charge (integer):", initialvalue=0)

        files = {}
        if pdb_file:
            files['pdb_file'] = (Path(pdb_file).name, open(pdb_file, 'rb'))
        if lig_file:
            files['ligand_file'] = (Path(lig_file).name, open(lig_file, 'rb'))

        try:
            r = self.client.post(f"{API_URL}/api/projects/{self.selected_project['id']}/upload",
                                 data={"ligand_charge": str(charge or 0)}, files=files)
            if r.status_code == 200:
                messagebox.showinfo("Upload", "Files uploaded and validated.")
                self.refresh_projects()
            else:
                messagebox.showerror("Upload error", f"{r.status_code}: {r.text}")
        finally:
            for f in files.values():
                try:
                    f[1].close()
                except Exception:
                    pass

    def start_job(self, mode: str):
        if not self.selected_project:
            messagebox.showwarning("Select project", "Please select a project first.")
            return
        payload = {"mode": mode}
        r = self.api("POST", f"/api/jobs/?project_id={self.selected_project['id']}", json=payload)
        if not r:
            return
        job = r.json()
        messagebox.showinfo("Job queued", f"Job {job['id']} queued with mode {mode}.")
        # Poll logs in background
        threading.Thread(target=self._poll_job_logs, args=(job['id'],), daemon=True).start()

    def _poll_job_logs(self, job_id: str):
        for _ in range(600):
            r = self.api("GET", f"/api/jobs/{job_id}")
            if not r:
                return
            job = r.json()
            r2 = self.api("GET", f"/api/jobs/{job_id}/logs")
            if r2:
                data = r2.json().get("log") if r2.headers.get("content-type", "").startswith("application/json") else r2.text
                self.logs.delete("1.0", tk.END)
                self.logs.insert(tk.END, data)
            if job.get("status") in ("success", "failed", "cancelled"):
                messagebox.showinfo("Job finished", f"Job {job_id} finished with status {job.get('status')}")
                self.refresh_projects()
                return
            time.sleep(2)


def main():
    # Start backend if needed
    if not is_port_in_use(8000):
        th = threading.Thread(target=run_server, daemon=True)
        th.start()
        # wait
        for _ in range(30):
            if is_port_in_use(8000):
                break
            time.sleep(0.2)

    root = tk.Tk()
    app = BindCraftGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
