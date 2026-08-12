/**
 * review.js — Review settings, warnings, code previews, and mode selection.
 */
async function renderReview(container, params = {}) {
  const projectId = params.projectId || BC.currentProject?.id;
  if (!projectId) { navigate('dashboard'); return; }

  let project = BC.currentProject?.id === projectId ? BC.currentProject : null;
  if (!project) {
    try { project = await window.API.get(`/projects/${projectId}`); BC.currentProject = project; }
    catch { showToast('Could not load project', 'error'); navigate('dashboard'); return; }
  }

  let settings = {};
  try { settings = JSON.parse(project.settings_json || '{}'); } catch {}

  // 1. Re-validate to get atom counts and warnings
  let validation = null;
  try {
    validation = await window.API.get(`/projects/${projectId}/validate`);
  } catch (e) {
    console.warn("Validation failed on review page", e);
  }

  // 2. Mock template generation for preview (backend doesn't have an endpoint for this yet,
  //    so we'll just show placeholders or say it'll be generated).
  //    In a real app we'd have a /projects/{id}/preview endpoint. We'll add static placeholders.

  const wslOk = BC.systemStatus?.wsl_available;
  const amberOk = BC.systemStatus?.ambertools_available;

  container.innerHTML = `
    <div class="page">
      <div class="container-sm">
        <div class="section-header">
          <div class="section-icon">✅</div>
          <div>
            <div class="section-title">Review & Confirm</div>
            <div class="section-sub">${escHtml(project.name)}</div>
          </div>
        </div>

        <!-- Validation Warnings -->
        ${validation && validation.warnings.length > 0 ? `
          <div class="warnings-panel">
            <div class="warnings-panel-header">
              ⚠️ Validation Notes
            </div>
            ${validation.warnings.map(w => `
              <div class="warning-entry ${w.level}">
                <div>
                  <strong>${escHtml(w.message)}</strong>
                  <div class="text-muted mt-2">${escHtml(w.detail || '')}</div>
                </div>
              </div>
            `).join('')}
          </div>
        ` : ''}

        <!-- Summary Accordions -->
        <div class="card mb-6" style="padding:0; overflow:hidden;">
          <div class="accordion-item open" style="margin:0; border:none; border-bottom:1px solid var(--border-subtle); border-radius:0;">
            <div class="accordion-header">
              <span>📋 Project & Files</span>
              <span class="accordion-chevron">▼</span>
            </div>
            <div class="accordion-body">
              <div class="grid-2">
                <div>
                  <div class="text-xs text-muted uppercase tracking-wider mb-2">Complex</div>
                  <div class="font-mono text-sm">${project.pdb_filename || 'None'}</div>
                </div>
                <div>
                  <div class="text-xs text-muted uppercase tracking-wider mb-2">Ligand</div>
                  <div class="font-mono text-sm">${project.ligand_filename || 'Extracted from PDB'}</div>
                  <div class="text-sm mt-2">Residue: <span class="tag">${project.ligand_name}</span> | Charge: <strong>${project.ligand_charge}</strong></div>
                </div>
              </div>
            </div>
          </div>

          <div class="accordion-item" style="margin:0; border:none; border-bottom:1px solid var(--border-subtle); border-radius:0;">
            <div class="accordion-header">
              <span>⚙️ Parameters</span>
              <span class="accordion-chevron">▼</span>
            </div>
            <div class="accordion-body">
              <div class="grid-3">
                <div>
                  <div class="text-xs text-muted uppercase tracking-wider mb-2">Force Fields</div>
                  <div class="text-sm">Protein: ${settings.protein_ff}</div>
                  <div class="text-sm">Ligand: ${settings.ligand_ff}</div>
                  <div class="text-sm">Water: ${settings.water_model}</div>
                </div>
                <div>
                  <div class="text-xs text-muted uppercase tracking-wider mb-2">Environment</div>
                  <div class="text-sm">Solvent: ${settings.solvent_type}</div>
                  <div class="text-sm">Temp: ${settings.temperature} K</div>
                  ${settings.solvent_type === 'explicit' ? `<div class="text-sm">Pressure: ${settings.pressure} atm</div>` : ''}
                </div>
                <div>
                  <div class="text-xs text-muted uppercase tracking-wider mb-2">Simulation</div>
                  <div class="text-sm">Preset: ${settings.preset}</div>
                  <div class="text-sm">Output freq: ${settings.output_freq}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <h3 class="mb-4">🚀 Select Execution Mode</h3>
        <div class="mode-grid" id="mode-selector">
          <!-- Demo -->
          <div class="mode-card" data-mode="demo">
            <div class="mode-icon">🧪</div>
            <div class="mode-name">Demo Mode</div>
            <div class="mode-desc">Load pre-built AChE results. No software needed.</div>
          </div>

          <!-- Generate -->
          <div class="mode-card selected" data-mode="generate">
            <div class="mode-icon">📦</div>
            <div class="mode-name">Generate Only</div>
            <div class="mode-desc">Create input files & download ZIP. Run manually later.</div>
          </div>

          <!-- Run -->
          <div class="mode-card ${(!wslOk || !amberOk) ? 'disabled' : ''}" data-mode="run"
               title="${(!wslOk || !amberOk) ? 'WSL or AmberTools not found on this system.' : ''}">
            <div class="mode-icon">⚡</div>
            <div class="mode-name">Run Local</div>
            <div class="mode-desc">Execute full pipeline via WSL2 in the background.</div>
            ${(!wslOk || !amberOk) ? '<div class="text-xs text-danger mt-2">Unavailable</div>' : ''}
          </div>
        </div>

        <div class="confirm-row">
          <input type="checkbox" id="confirm-check" class="confirm-checkbox" />
          <label for="confirm-check" class="confirm-label">
            I understand that BindCraft does not perform docking, and that these results are for educational purposes only.
          </label>
        </div>

        <!-- Action Bar -->
        <div class="action-bar">
          <button class="btn btn-ghost" onclick="navigate('wizard', {projectId: '${projectId}'})">← Back</button>
          <button class="btn btn-primary" id="btn-submit" disabled>Start Generation →</button>
        </div>
      </div>
    </div>
  `;

  initAccordions();

  let selectedMode = 'generate';

  // Mode Selection
  document.getElementById('mode-selector').addEventListener('click', e => {
    const card = e.target.closest('.mode-card');
    if (!card || card.classList.contains('disabled')) return;

    document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    selectedMode = card.dataset.mode;

    const btn = document.getElementById('btn-submit');
    if (selectedMode === 'run') btn.textContent = 'Start Simulation ⚡';
    else if (selectedMode === 'demo') btn.textContent = 'Load Demo 🧪';
    else btn.textContent = 'Start Generation 📦';
  });

  // Checkbox toggle
  const check = document.getElementById('confirm-check');
  const submitBtn = document.getElementById('btn-submit');
  check.addEventListener('change', () => {
    submitBtn.disabled = !check.checked;
  });

  // Submit
  submitBtn.addEventListener('click', async () => {
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Starting...';

    // If demo mode is selected but this isn't the demo project, we can't really "run" demo mode
    // on a real project. But we will let the backend handle it or redirect.
    // Actually, if they choose demo, just navigate to results with demo ID.
    if (selectedMode === 'demo') {
      navigate('results', { projectId: 'demo-acetylcholinesterase' });
      return;
    }

    try {
      const job = await window.API.post(`/jobs/?project_id=${projectId}`, { mode: selectedMode });
      BC.currentJob = job;
      navigate('results', { projectId });
    } catch (e) {
      showToast(`Failed to start job: ${e.message}`, 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Try Again';
    }
  });
}
