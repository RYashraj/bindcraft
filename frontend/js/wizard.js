/**
 * wizard.js — Setup Wizard: parameter configuration with explanations.
 */
const PRESET_INFO = {
  fast_test: {
    label: 'Fast Learning Test',
    icon: '⚡',
    steps: 'Minimization + 10 ps heating + 20 ps equilibration + 50 ps production',
    note: 'Great for first runs. Completes in ~20 min on CPU. Results are illustrative.',
    tags: ['~20 min', 'CPU OK', 'Beginner'],
  },
  basic_test: {
    label: 'Basic Test',
    icon: '📊',
    steps: 'Minimization + 20 ps heating + 100 ps equilibration + 100 ps production',
    note: 'More data for analysis. Expect ~90 min on CPU. Better for trend visualisation.',
    tags: ['~90 min', 'CPU OK', 'Intermediate'],
  },
};

async function renderWizard(container, params = {}) {
  const projectId = params.projectId || BC.currentProject?.id;
  if (!projectId) { navigate('dashboard'); return; }

  let project = BC.currentProject?.id === projectId ? BC.currentProject : null;
  if (!project) {
    try { project = await window.API.get(`/projects/${projectId}`); BC.currentProject = project; }
    catch { showToast('Could not load project', 'error'); navigate('dashboard'); return; }
  }

  // Existing settings
  let saved = {};
  try { if (project.settings_json) saved = JSON.parse(project.settings_json); } catch {}

  // Defaults
  const defaults = {
    solvent_type: 'explicit',
    temperature: 300,
    pressure: 1.0,
    box_padding: 10,
    preset: 'fast_test',
    output_freq: 500,
    ...saved,
  };

  container.innerHTML = `
    <div class="page">
      <div class="container-sm">
        <div class="section-header">
          <div class="section-icon">⚙️</div>
          <div>
            <div class="section-title">Setup Wizard</div>
            <div class="section-sub">${escHtml(project.name)}</div>
          </div>
        </div>

        <!-- Force Fields (locked) -->
        <div class="card mb-6">
          <h3 class="mb-4">🔬 Force Fields <span class="badge badge-configured" style="margin-left:8px">v1 defaults</span></h3>
          <div class="grid-3" style="gap:var(--space-3)">
            ${ffCard('Protein Force Field', 'ff14SB', 'Best-practice for proteins in AmberTools. Validated for most amino acids.')}
            ${ffCard('Ligand Force Field', 'GAFF2', 'General Amber Force Field v2. Auto-parameterises small organic molecules.')}
            ${ffCard('Water Model', 'TIP3P', 'Three-point explicit water. Fast and widely used for protein-ligand systems.')}
          </div>
          <div class="param-explain mt-4">
            ℹ️ These force fields are fixed in BindCraft v1 to ensure reliable results for beginners.
            They represent the recommended combination for protein–ligand simulations in AmberTools.
          </div>
        </div>

        <!-- Solvent -->
        <div class="card mb-6">
          <h3 class="mb-4">💧 Solvent Model</h3>
          <div class="preset-grid" id="solvent-grid">
            ${solventCard('explicit', 'Explicit Water', 'TIP3P molecules surround the system.',
              ['More realistic', 'Larger system', 'Slower'], defaults.solvent_type === 'explicit')}
            ${solventCard('implicit', 'Implicit Solvent', 'GB/SA continuum model — no water molecules.',
              ['Faster', 'Less memory', 'Less accurate'], defaults.solvent_type === 'implicit')}
          </div>
          <div id="solvent-explicit-opts" class="${defaults.solvent_type === 'explicit' ? '' : 'hidden'}">
            <div class="form-group mt-4">
              <label class="form-label" for="box-padding">
                Box Padding
                <span class="tooltip-wrap">
                  <span class="tooltip-icon">?</span>
                  <span class="tooltip-text">Distance between the protein surface and the water box edge.
10 Å is standard. Larger = more water = slower but better periodic boundary.</span>
                </span>
              </label>
              <div class="flex items-center gap-4">
                <input type="range" class="form-range" id="box-padding"
                  min="8" max="18" step="0.5" value="${defaults.box_padding}" data-unit=" Å" />
                <span class="range-value" data-for="box-padding">${defaults.box_padding} Å</span>
              </div>
              <div class="form-hint">Standard: 10 Å. Increase for flexible proteins.</div>
            </div>
          </div>
        </div>

        <!-- Conditions -->
        <div class="card mb-6">
          <h3 class="mb-4">🌡️ Simulation Conditions</h3>
          <div class="form-group">
            <label class="form-label" for="temperature">
              Temperature
              <span class="tooltip-wrap">
                <span class="tooltip-icon">?</span>
                <span class="tooltip-text">Target temperature in Kelvin.
300 K ≈ 27°C (physiological temperature).
The Langevin thermostat maintains this temperature throughout the simulation.</span>
              </span>
            </label>
            <div class="flex items-center gap-4">
              <input type="range" class="form-range" id="temperature"
                min="200" max="400" step="5" value="${defaults.temperature}" data-unit=" K" />
              <span class="range-value" data-for="temperature">${defaults.temperature} K</span>
            </div>
            <div class="form-hint">Physiological: 300 K. Increase for enhanced sampling (advanced).</div>
          </div>

          <div class="form-group" id="pressure-group" style="${defaults.solvent_type === 'implicit' ? 'display:none' : ''}">
            <label class="form-label" for="pressure">
              Pressure
              <span class="tooltip-wrap">
                <span class="tooltip-icon">?</span>
                <span class="tooltip-text">Target pressure in atmospheres for NPT ensemble.
1.0 atm = standard physiological pressure.
Only applies to explicit solvent (NPT equilibration and production).</span>
              </span>
            </label>
            <div class="flex items-center gap-4">
              <input type="range" class="form-range" id="pressure"
                min="0.5" max="2.0" step="0.1" value="${defaults.pressure}" data-unit=" atm" />
              <span class="range-value" data-for="pressure">${defaults.pressure} atm</span>
            </div>
            <div class="form-hint">Standard: 1.0 atm.</div>
          </div>
        </div>

        <!-- Simulation Preset -->
        <div class="card mb-6">
          <h3 class="mb-4">🎯 Simulation Preset</h3>
          <div class="preset-grid" id="preset-grid">
            ${Object.entries(PRESET_INFO).map(([k, v]) =>
              presetCard(k, v, defaults.preset === k)).join('')}
          </div>
        </div>

        <!-- Output Frequency -->
        <div class="card mb-6">
          <h3 class="mb-4">📤 Output Frequency</h3>
          <div class="form-group">
            <label class="form-label" for="output-freq">
              Save coordinates every N steps
              <span class="tooltip-wrap">
                <span class="tooltip-icon">?</span>
                <span class="tooltip-text">How often to write the trajectory (mdcrd) and energy (mdout).
500 steps = 1 ps with dt=0.002 ps.
More frequent = larger files but more data for analysis.</span>
              </span>
            </label>
            <div class="flex items-center gap-4">
              <input type="range" class="form-range" id="output-freq"
                min="100" max="5000" step="100" value="${defaults.output_freq}" data-unit=" steps" />
              <span class="range-value" data-for="output-freq">${defaults.output_freq} steps</span>
            </div>
            <div class="form-hint">500 steps = 1 ps output interval (recommended for learning).</div>
          </div>
        </div>

        <!-- Action Bar -->
        <div class="action-bar">
          <button class="btn btn-ghost" onclick="navigate('new-project', {projectId: '${projectId}'})">← Back</button>
          <button class="btn btn-primary" id="btn-next-review">Review & Confirm →</button>
        </div>
      </div>
    </div>
  `;

  initRangeSliders();

  // Solvent toggle
  let solventType = defaults.solvent_type;
  document.getElementById('solvent-grid').addEventListener('click', e => {
    const card = e.target.closest('[data-solvent]');
    if (!card) return;
    solventType = card.dataset.solvent;
    document.querySelectorAll('[data-solvent]').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    document.getElementById('solvent-explicit-opts').classList.toggle('hidden', solventType !== 'explicit');
    document.getElementById('pressure-group').style.display = solventType === 'explicit' ? '' : 'none';
  });

  // Preset toggle
  let selectedPreset = defaults.preset;
  document.getElementById('preset-grid').addEventListener('click', e => {
    const card = e.target.closest('[data-preset]');
    if (!card) return;
    selectedPreset = card.dataset.preset;
    document.querySelectorAll('[data-preset]').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    card.querySelector('.preset-card-check').style.display = 'flex';
  });

  // Next button
  document.getElementById('btn-next-review').addEventListener('click', async () => {
    const settings = {
      protein_ff: 'ff14SB',
      ligand_ff: 'GAFF2',
      water_model: 'TIP3P',
      solvent_type: solventType,
      box_padding: parseFloat(document.getElementById('box-padding')?.value || '10'),
      temperature: parseFloat(document.getElementById('temperature').value),
      pressure: parseFloat(document.getElementById('pressure')?.value || '1.0'),
      preset: selectedPreset,
      output_freq: parseInt(document.getElementById('output-freq').value),
    };

    const btn = document.getElementById('btn-next-review');
    btn.disabled = true; btn.textContent = '⏳ Saving…';

    try {
      await window.API.put(`/projects/${projectId}/settings`, settings);
      BC.currentProject = await window.API.get(`/projects/${projectId}`);
      navigate('review', { projectId });
    } catch (e) {
      showToast(`Failed to save settings: ${e.message}`, 'error');
    } finally {
      btn.disabled = false; btn.textContent = 'Review & Confirm →';
    }
  });
}

function ffCard(label, value, explain) {
  return `
    <div class="card" style="padding:var(--space-4);border-color:var(--border-accent);background:rgba(129,140,248,.04)">
      <div class="text-xs" style="color:var(--text-muted);text-transform:uppercase;font-weight:700;letter-spacing:.06em;margin-bottom:6px">${label}</div>
      <div style="font-size:1.1rem;font-weight:800;color:var(--accent-primary)">${value}</div>
      <div class="text-xs mt-2" style="color:var(--text-muted)">${explain}</div>
    </div>`;
}

function solventCard(id, name, desc, tags, selected) {
  return `
    <div class="preset-card ${selected ? 'selected' : ''}" data-solvent="${id}">
      <div class="preset-card-check">✓</div>
      <div class="preset-title">${id === 'explicit' ? '💧' : '🌫️'} ${name}</div>
      <div class="preset-desc">${desc}</div>
      <div class="preset-tags">${tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>
    </div>`;
}

function presetCard(key, info, selected) {
  return `
    <div class="preset-card ${selected ? 'selected' : ''}" data-preset="${key}">
      <div class="preset-card-check" style="${selected ? 'display:flex' : ''}">✓</div>
      <div class="preset-title">${info.icon} ${info.label}</div>
      <div class="preset-desc">${info.steps}</div>
      <div class="text-xs mt-2" style="color:var(--accent-info)">${info.note}</div>
      <div class="preset-tags mt-2">${info.tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>
    </div>`;
}
