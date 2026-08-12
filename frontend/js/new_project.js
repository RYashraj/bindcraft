/**
 * new_project.js — Upload files, enter metadata, validate.
 */
async function renderNewProject(container, params = {}) {
  const existingId = params.projectId;
  let project = existingId ? (BC.currentProject?.id === existingId ? BC.currentProject : null) : null;

  if (existingId && !project) {
    try { project = await window.API.get(`/projects/${existingId}`); BC.currentProject = project; }
    catch { showToast('Could not load project', 'error'); navigate('dashboard'); return; }
  }

  container.innerHTML = `
    <div class="page">
      <div class="container-sm">
        <div class="section-header">
          <div class="section-icon">🧬</div>
          <div>
            <div class="section-title">${project ? 'Edit Project' : 'New Project'}</div>
            <div class="section-sub">Upload your protein–ligand complex and enter basic info</div>
          </div>
        </div>

        <div class="disclaimer-box mb-6">
          <strong>📌 No Docking</strong> — BindCraft requires the ligand to be already placed
          in its binding site (HETATM records in the PDB). If your ligand is not yet positioned,
          please use AutoDock Vina or a co-crystal structure from RCSB PDB first.
        </div>

        <div class="card mb-6">
          <h3 class="mb-4">📝 Project Details</h3>
          <div class="form-group">
            <label class="form-label" for="proj-name">Project Name <span style="color:var(--accent-danger)">*</span></label>
            <input id="proj-name" class="form-input" type="text" placeholder="e.g. AChE-Donepezil_300K_TIP3P"
              maxlength="200" value="${project ? escHtml(project.name) : ''}" />
            <div class="form-hint">Give it a descriptive name including the protein, ligand, and conditions.</div>
          </div>
          <div class="form-group">
            <label class="form-label" for="proj-notes">Research Notes <span class="form-label-hint">optional</span></label>
            <textarea id="proj-notes" class="form-textarea" placeholder="Describe the scientific context, the drug, the target, or your learning goals…">${project ? escHtml(project.notes || '') : ''}</textarea>
          </div>
        </div>

        <div class="card mb-6">
          <h3 class="mb-4">📂 Upload Files</h3>

          <div class="grid-2 mb-4">
            <!-- PDB Upload -->
            <div class="form-group">
              <label class="form-label">Complex PDB <span style="color:var(--accent-danger)">*</span></label>
              <div class="upload-zone ${project?.pdb_filename ? 'has-file' : ''}" id="pdb-zone">
                <input type="file" id="pdb-input" accept=".pdb" />
                <div class="upload-icon">🧬</div>
                <div class="upload-title">Drop PDB file here</div>
                <div class="upload-hint">Complex PDB with protein + bound ligand (HETATM)</div>
                <div class="upload-file-name" id="pdb-file-name">${project?.pdb_filename || ''}</div>
              </div>
            </div>

            <!-- Ligand Upload -->
            <div class="form-group">
              <label class="form-label">Ligand SDF or MOL2
                <span class="form-label-hint">recommended</span>
              </label>
              <div class="upload-zone ${project?.ligand_filename ? 'has-file' : ''}" id="lig-zone">
                <input type="file" id="lig-input" accept=".sdf,.mol2" />
                <div class="upload-icon">💊</div>
                <div class="upload-title">Drop SDF or MOL2 here</div>
                <div class="upload-hint">Ligand structure for GAFF2 parameterisation</div>
                <div class="upload-file-name" id="lig-file-name">${project?.ligand_filename || ''}</div>
              </div>
            </div>
          </div>

          <div class="form-group" style="max-width:300px">
            <label class="form-label" for="charge-input">
              Ligand Net Charge
              <span style="color:var(--accent-danger)">*</span>
              <span class="tooltip-wrap">
                <span class="tooltip-icon">?</span>
                <span class="tooltip-text">The total formal charge on the ligand molecule.
Most drug-like molecules are 0, +1, or -1.
Check your ligand's structure or ChemDraw/MarvinSketch.
antechamber needs this to assign partial charges correctly.</span>
              </span>
            </label>
            <input id="charge-input" class="form-input" type="number"
              min="-4" max="4" step="1"
              value="${project?.ligand_charge ?? 0}" />
            <div class="form-hint">Integer — use 0 for neutral, +1 for cations, -1 for anions.</div>
          </div>

          <button class="btn btn-secondary" id="btn-validate">
            🔍 Validate Files
          </button>
        </div>

        <!-- Validation Results -->
        <div id="validation-area" class="mb-6" style="display:none">
          <div class="validation-panel" id="validation-panel"></div>
        </div>

        <!-- Action Bar -->
        <div class="action-bar">
          <button class="btn btn-ghost" onclick="navigate('dashboard')">← Back</button>
          <div class="flex gap-3">
            <button class="btn btn-secondary" id="btn-save">💾 Save</button>
            <button class="btn btn-primary" id="btn-next" disabled>Setup Wizard →</button>
          </div>
        </div>
      </div>
    </div>
  `;

  // State
  let pdbFile = null;
  let ligFile = null;
  let currentProjectId = project?.id || null;
  let validationPassed = !!project?.pdb_filename;

  // File drag-and-drop setup
  setupDropZone('pdb-zone', 'pdb-input', '.pdb', f => { pdbFile = f; updateZone('pdb-zone', 'pdb-file-name', f.name); });
  setupDropZone('lig-zone', 'lig-input', '.sdf,.mol2', f => { ligFile = f; updateZone('lig-zone', 'lig-file-name', f.name); });

  // Validate button
  document.getElementById('btn-validate').addEventListener('click', async () => {
    const name = document.getElementById('proj-name').value.trim();
    if (!name) { showToast('Please enter a project name.', 'warning'); return; }
    if (!pdbFile && !project?.pdb_filename) { showToast('Please select a PDB file.', 'warning'); return; }

    const btn = document.getElementById('btn-validate');
    btn.disabled = true;
    btn.textContent = '⏳ Validating…';

    try {
      // Create project if needed
      if (!currentProjectId) {
        const p = await window.API.post('/projects/', {
          name,
          notes: document.getElementById('proj-notes').value.trim() || null,
        });
        currentProjectId = p.id;
        BC.currentProject = p;
      }

      // Upload files
      const form = new FormData();
      if (pdbFile) form.append('pdb_file', pdbFile);
      if (ligFile) form.append('ligand_file', ligFile);
      form.append('ligand_charge', document.getElementById('charge-input').value);

      const result = await window.API.upload(`/projects/${currentProjectId}/upload`, form);
      BC.currentProject = await window.API.get(`/projects/${currentProjectId}`);

      renderValidationPanel(result);
      validationPassed = result.valid;
      document.getElementById('btn-next').disabled = !result.valid;

    } catch (e) {
      showToast(e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '🔍 Validate Files';
    }
  });

  // Save button
  document.getElementById('btn-save').addEventListener('click', async () => {
    const name = document.getElementById('proj-name').value.trim();
    if (!name) { showToast('Please enter a project name.', 'warning'); return; }

    if (!currentProjectId) {
      try {
        const p = await window.API.post('/projects/', {
          name,
          notes: document.getElementById('proj-notes').value.trim() || null,
        });
        currentProjectId = p.id;
        BC.currentProject = p;
        showToast('Project created!', 'success');
      } catch (e) { showToast(e.message, 'error'); }
    } else {
      showToast('Project saved.', 'success');
    }
  });

  // Next button
  document.getElementById('btn-next').addEventListener('click', () => {
    if (!currentProjectId) { showToast('Please validate files first.', 'warning'); return; }
    navigate('wizard', { projectId: currentProjectId });
  });
}

function renderValidationPanel(result) {
  const area  = document.getElementById('validation-area');
  const panel = document.getElementById('validation-panel');
  area.style.display = 'block';

  const icons = { info: 'ℹ️', warning: '⚠️', error: '❌' };

  const headerColor = result.valid ? 'var(--accent-success)' : 'var(--accent-danger)';
  const headerText  = result.valid
    ? `✅ Validation passed — ${result.atom_count || ''} atoms, ${result.residue_count || ''} residues`
    : '❌ Validation failed — fix errors before proceeding';

  const stats = [
    result.atom_count ? `${result.atom_count} atoms` : null,
    result.residue_count ? `${result.residue_count} residues` : null,
    result.ligand_residue ? `Ligand: ${result.ligand_residue}` : null,
    result.has_hydrogens !== null ? (result.has_hydrogens ? 'Hydrogens ✓' : 'No H detected') : null,
  ].filter(Boolean);

  panel.innerHTML = `
    <div class="validation-header" style="color:${headerColor}">
      ${headerText}
      ${stats.length ? `<span class="text-muted" style="font-weight:400;margin-left:8px">${stats.join(' · ')}</span>` : ''}
    </div>
    ${result.warnings.map(w => `
      <div class="validation-item ${w.level}">
        <span class="val-icon">${icons[w.level] || 'ℹ️'}</span>
        <div class="val-content">
          <div class="val-message">${escHtml(w.message)}</div>
          ${w.detail ? `<div class="val-detail">${escHtml(w.detail)}</div>` : ''}
        </div>
      </div>`).join('')}
  `;
}

function setupDropZone(zoneId, inputId, accept, onFile) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  input.setAttribute('accept', accept);

  input.addEventListener('change', () => {
    const f = input.files?.[0];
    if (f) onFile(f);
  });

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragging'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragging');
    const f = e.dataTransfer.files?.[0];
    if (f) { onFile(f); }
  });
}

function updateZone(zoneId, nameId, filename) {
  const zone = document.getElementById(zoneId);
  const name = document.getElementById(nameId);
  if (zone) zone.classList.add('has-file');
  if (name) name.textContent = filename;
}
