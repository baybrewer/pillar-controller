// Pillar Controller — Frontend Application

const API = '';  // Same origin
let ws = null;
let state = {};

// --- WebSocket ---

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    document.getElementById('connection-dot').className = 'dot connected';
  };

  ws.onclose = () => {
    document.getElementById('connection-dot').className = 'dot disconnected';
    setTimeout(connectWS, 2000);
  };

  ws.onerror = () => {
    ws.close();
  };

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      updateState(data);
    } catch (e) {}
  };
}

function updateState(data) {
  state = { ...state, ...data };

  // FPS
  const fpsEl = document.getElementById('fps-display');
  if (data.actual_fps !== undefined) {
    fpsEl.textContent = `${data.actual_fps} FPS`;
  }

  // Scene name
  const sceneEl = document.getElementById('current-scene-name');
  if (data.current_scene) {
    sceneEl.textContent = data.current_scene.replace(/_/g, ' ');
  }

  // Blackout button
  const bbtn = document.getElementById('blackout-btn');
  if (data.blackout) {
    bbtn.classList.add('active');
  } else {
    bbtn.classList.remove('active');
  }

  // Brightness
  if (data.brightness !== undefined) {
    const slider = document.getElementById('brightness-slider');
    slider.value = Math.round(data.brightness * 100);
    document.getElementById('brightness-value').textContent = `${slider.value}%`;
  }

  // Audio meters
  if (data.audio_level !== undefined) {
    updateMeter('meter-bass', state.audio_bass || 0);
    updateMeter('meter-mid', state.audio_mid || 0);
    updateMeter('meter-high', state.audio_high || 0);
  }
}

function updateMeter(id, value) {
  const el = document.getElementById(id);
  if (el) {
    el.style.setProperty('--level', `${Math.min(100, value * 100)}%`);
    const after = el.querySelector('::after');
    // Use inline style on a child or pseudo approach
    el.setAttribute('style', `--level: ${Math.min(100, value * 100)}%`);
  }
}

// --- API helpers ---

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  try {
    const res = await fetch(`${API}${path}`, opts);
    return await res.json();
  } catch (e) {
    console.error(`API error: ${method} ${path}`, e);
    return null;
  }
}

// --- Tab navigation ---

function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`panel-${tab.dataset.tab}`).classList.add('active');

      // Load tab-specific data
      if (tab.dataset.tab === 'effects') loadEffects();
      if (tab.dataset.tab === 'media') loadMedia();
      if (tab.dataset.tab === 'audio') loadAudioDevices();
      if (tab.dataset.tab === 'diag') loadStats();
      if (tab.dataset.tab === 'system') loadSystemStatus();
    });
  });
}

// --- Effects ---

async function loadEffects() {
  const data = await api('GET', '/api/scenes/list');
  if (!data) return;

  const genList = document.getElementById('effect-list');
  const audioList = document.getElementById('audio-effect-list');
  genList.innerHTML = '';
  audioList.innerHTML = '';

  for (const [name, info] of Object.entries(data.effects)) {
    if (name.startsWith('diag_')) continue;
    const btn = document.createElement('button');
    btn.textContent = name.replace(/_/g, ' ');
    if (name === data.current) btn.classList.add('active-scene');
    btn.addEventListener('click', () => activateEffect(name));
    if (info.type === 'audio') {
      audioList.appendChild(btn);
    } else {
      genList.appendChild(btn);
    }
  }
}

async function activateEffect(name) {
  await api('POST', '/api/scenes/activate', { effect: name, params: {} });
  loadEffects();
}

// --- Presets ---

async function loadPresets() {
  const data = await api('GET', '/api/scenes/presets');
  if (!data) return;

  const grid = document.getElementById('preset-grid');
  grid.innerHTML = '';

  for (const [name, scene] of Object.entries(data)) {
    const btn = document.createElement('button');
    btn.textContent = name;
    btn.addEventListener('click', () => loadPreset(name));
    grid.appendChild(btn);
  }
}

async function loadPreset(name) {
  await api('POST', `/api/scenes/presets/load/${encodeURIComponent(name)}`);
}

// --- Media ---

async function loadMedia() {
  const data = await api('GET', '/api/media/list');
  if (!data) return;

  const lib = document.getElementById('media-library');
  lib.innerHTML = '';

  for (const item of data.items) {
    const btn = document.createElement('button');
    btn.textContent = `${item.name}\n${item.type} · ${item.frame_count}f`;
    btn.addEventListener('click', () => playMedia(item.id));
    lib.appendChild(btn);
  }
}

async function playMedia(itemId) {
  await api('POST', `/api/media/play/${itemId}?loop=true&speed=1.0`);
}

// --- Upload ---

function initUpload() {
  const btn = document.getElementById('upload-btn');
  const input = document.getElementById('media-upload');

  btn.addEventListener('click', async () => {
    const file = input.files[0];
    if (!file) return;

    const progress = document.getElementById('upload-progress');
    progress.classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/media/upload', { method: 'POST', body: formData });
      const data = await res.json();
      if (data.status === 'ok') {
        input.value = '';
        loadMedia();
      }
    } catch (e) {
      console.error('Upload failed', e);
    }

    progress.classList.add('hidden');
  });
}

// --- Audio ---

async function loadAudioDevices() {
  const data = await api('GET', '/api/audio/devices');
  if (!data) return;

  const select = document.getElementById('audio-device-select');
  select.innerHTML = '<option value="">Default</option>';
  for (const dev of data.devices) {
    const opt = document.createElement('option');
    opt.value = dev.index;
    opt.textContent = dev.name;
    select.appendChild(opt);
  }
}

function initAudio() {
  document.getElementById('audio-start-btn').addEventListener('click', () => {
    api('POST', '/api/audio/start');
  });

  document.getElementById('audio-stop-btn').addEventListener('click', () => {
    api('POST', '/api/audio/stop');
  });

  document.getElementById('audio-sensitivity').addEventListener('change', (e) => {
    const val = e.target.value / 100;
    api('POST', '/api/audio/config', { sensitivity: val });
  });

  document.getElementById('audio-gain').addEventListener('change', (e) => {
    const val = e.target.value / 100;
    api('POST', '/api/audio/config', { gain: val });
  });
}

// --- Diagnostics ---

function initDiagnostics() {
  document.querySelectorAll('.test-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      api('POST', '/api/diagnostics/test-pattern', { pattern: btn.dataset.test });
    });
  });
}

async function loadStats() {
  const data = await api('GET', '/api/diagnostics/stats');
  if (!data) return;
  document.getElementById('stats-output').textContent = JSON.stringify(data, null, 2);
}

// --- System ---

async function loadSystemStatus() {
  const data = await api('GET', '/api/system/status');
  if (!data) return;

  document.getElementById('sys-transport').textContent =
    data.transport?.connected ? `Connected (${data.transport.port})` : 'Disconnected';
  document.getElementById('sys-firmware').textContent =
    data.transport?.caps?.firmware_version || '--';
  document.getElementById('sys-frames').textContent =
    data.transport?.frames_sent?.toLocaleString() || '0';
}

function initSystem() {
  document.getElementById('fps-select').addEventListener('change', (e) => {
    api('POST', '/api/display/fps', { value: parseInt(e.target.value) });
  });

  document.getElementById('restart-app-btn').addEventListener('click', () => {
    if (confirm('Restart the pillar application?')) {
      api('POST', '/api/system/restart-app');
    }
  });

  document.getElementById('reboot-btn').addEventListener('click', () => {
    if (confirm('Reboot the Raspberry Pi?')) {
      api('POST', '/api/system/reboot');
    }
  });
}

// --- Brightness ---

function initBrightness() {
  const slider = document.getElementById('brightness-slider');
  const display = document.getElementById('brightness-value');

  let debounce = null;
  slider.addEventListener('input', () => {
    display.textContent = `${slider.value}%`;
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      api('POST', '/api/display/brightness', { value: slider.value / 100 });
    }, 100);
  });
}

// --- Blackout ---

function initBlackout() {
  document.getElementById('blackout-btn').addEventListener('click', () => {
    api('POST', '/api/display/blackout');
  });
}

// --- Init ---

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initBrightness();
  initBlackout();
  initUpload();
  initAudio();
  initDiagnostics();
  initSystem();
  connectWS();
  loadPresets();
});
