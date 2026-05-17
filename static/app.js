/* HedgeFund Analyser — frontend JS */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let currentRunId = null;
let activeSource = null;

// Per-phase selected model (keyed by "phase1","phase2","debate","pm")
const selectedModels = {
  phase1: 'gemini-2.0-flash',
  phase2: 'gemini-2.0-flash',
  debate: 'claude-opus-4-7',
  pm:     'claude-opus-4-7',
};

// Per-agent expand state: { [agentName]: { expanded, status, data, elapsedStart, timerId } }
const agentExpandState = {};

const SCORE_LABELS = { 1: 'Strong Buy', 2: 'Buy', 3: 'Neutral', 4: 'Sell', 5: 'Strong Sell' };

// Cost lookup: model → cost in pence (for estimate calculation)
const COST_TABLE = {
  'gemini-2.0-flash':       { cost: 0, label: 'FREE' },
  'claude-haiku-4-5-20251001': { cost: 3, label: '~£0.03' },
  'claude-opus-4-7':           { cost: 17, label: '~£0.17' },
  'claude-opus-4-6-20250514':  { cost: 12, label: '~£0.12' },
};

// ── Tab routing ───────────────────────────────────────────────────────────────
function showTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('pane-' + name).classList.remove('hidden');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'watchlist') loadWatchlist();
  if (name === 'runs') loadRuns();
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function openModal() {
  document.getElementById('config-modal').classList.remove('hidden');
  document.getElementById('ticker-input').focus();
}

function closeModal() {
  document.getElementById('config-modal').classList.add('hidden');
}

function onModalOverlayClick(e) {
  if (e.target === document.getElementById('config-modal')) closeModal();
}

function onTickerInput(input) {
  const val = input.value.trim();
  document.getElementById('start-btn').disabled = val.length === 0;
}

function selectModel(btn) {
  const phase = btn.dataset.phase;
  const model = btn.dataset.model;
  // Deselect siblings
  btn.closest('.model-cards-row').querySelectorAll('.model-card').forEach(c => c.classList.remove('selected'));
  btn.classList.add('selected');
  selectedModels[phase] = model;
  updateCostEstimate();
}

function updateCostEstimate() {
  const p1 = COST_TABLE[selectedModels.phase1] || { cost: 0, label: 'FREE' };
  const p2 = COST_TABLE[selectedModels.phase2] || { cost: 0, label: 'FREE' };
  const db = COST_TABLE[selectedModels.debate] || { cost: 17, label: '~£0.17' };
  const pm = COST_TABLE[selectedModels.pm]     || { cost: 17, label: '~£0.17' };

  const totalPence = p1.cost + p2.cost + db.cost + pm.cost;
  const totalStr = totalPence === 0 ? 'FREE' : `~£${(totalPence / 100).toFixed(2)}`;
  document.getElementById('cost-estimate').textContent = totalStr;
}

// ── Analysis ──────────────────────────────────────────────────────────────────
function startAnalysis() {
  const ticker = document.getElementById('ticker-input').value.trim().toUpperCase();
  if (!ticker) return;

  closeModal();
  resetProgressPanel(ticker);
  document.getElementById('progress-panel').classList.remove('hidden');

  if (activeSource) activeSource.close();

  fetch('/analyse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ticker,
      phase1_model: selectedModels.phase1,
      phase2_model: selectedModels.phase2,
      debate_model: selectedModels.debate,
      pm_model:     selectedModels.pm,
    }),
  }).then(res => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    function pump() {
      reader.read().then(({ done, value }) => {
        if (done) { onStreamDone(); return; }
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        lines.forEach(line => {
          if (line.startsWith('data: ')) {
            try { handleEvent(JSON.parse(line.slice(6))); } catch (_) {}
          }
        });
        pump();
      });
    }
    pump();
  }).catch(err => {
    showError('Connection failed: ' + err.message);
  });
}

function resetProgressPanel(ticker) {
  currentRunId = null;

  // Clear expand state and timers
  Object.values(agentExpandState).forEach(s => { if (s.timerId) clearInterval(s.timerId); });
  Object.keys(agentExpandState).forEach(k => delete agentExpandState[k]);

  document.getElementById('run-ticker').textContent = ticker;
  document.getElementById('run-id-badge').textContent = 'run #–';
  document.getElementById('run-status-badge').textContent = 'Running';
  document.getElementById('run-status-badge').className =
    'text-xs px-3 py-1 rounded-full bg-yellow-900 text-yellow-300';

  ['p1','p2','p3','p4'].forEach(p => {
    const s = document.getElementById(p + '-status');
    if (s) { s.textContent = 'Waiting'; s.className = 'phase-status text-xs text-gray-500'; }
    const ex = document.getElementById(p + '-expand');
    if (ex) ex.innerHTML = '';
    const ag = document.getElementById(p + '-agents');
    if (ag) ag.innerHTML = '';
    const mt = document.getElementById(p + '-model-tag');
    if (mt) mt.textContent = '';
  });
  document.getElementById('debate-feed').innerHTML = '';
  document.getElementById('debate-summary').classList.add('hidden');
  document.getElementById('pm-output').innerHTML = '';
  document.getElementById('verdict-card').classList.add('hidden');
  document.getElementById('abort-card').classList.add('hidden');
  document.getElementById('upload-zone').classList.add('hidden');
}

// ── SSE event handler ─────────────────────────────────────────────────────────
function handleEvent(ev) {
  switch (ev.event) {
    case 'run_start':
    case 'run_resume':
      currentRunId = ev.run_id;
      document.getElementById('run-id-badge').textContent = 'run #' + ev.run_id;
      // Update model tags from selected config
      setModelTag('p1', selectedModels.phase1);
      setModelTag('p2', selectedModels.phase2);
      setModelTag('p3', selectedModels.debate);
      setModelTag('p4', selectedModels.pm);
      break;

    case 'fetch_start':
      setPhaseStatus('p1', 'Fetching data…', 'text-indigo-400');
      break;

    case 'fetch_complete':
      setPhaseStatus('p1', 'Data ready', 'text-indigo-400');
      break;

    case 'phase_start':
      onPhaseStart(ev);
      break;

    case 'agent_log':
      onAgentLog(ev);
      break;

    case 'agent_complete':
      onAgentComplete(ev);
      break;

    case 'phase_complete':
      onPhaseComplete(ev);
      break;

    case 'debate_round':
      onDebateRound(ev);
      break;

    case 'debate_complete':
      onDebateComplete(ev);
      break;

    case 'verdict':
      onVerdict(ev);
      break;

    case 'complete':
      onComplete(ev);
      break;

    case 'abort':
      onAbort(ev);
      break;

    case 'error':
      showError(ev.message);
      break;
  }
}

// ── Model tag helper ──────────────────────────────────────────────────────────
function setModelTag(phaseKey, model) {
  const el = document.getElementById(phaseKey + '-model-tag');
  if (!el) return;
  const short = modelShortName(model);
  el.textContent = short ? '(' + short + ')' : '';
}

function modelShortName(model) {
  if (!model) return '';
  if (model.startsWith('gemini')) return 'Gemini Flash';
  if (model.includes('haiku')) return 'Haiku 4.5';
  if (model.includes('opus-4-7')) return 'Opus 4.7';
  if (model.includes('opus-4-6')) return 'Opus 4.6';
  return model;
}

// ── Phase handlers ────────────────────────────────────────────────────────────
function onPhaseStart(ev) {
  const key = 'p' + ev.phase;
  setPhaseStatus(key, '<span class="spinner"></span> Running', 'text-indigo-400');

  if (ev.phase === 1) renderAgentChips('p1-agents', ev.agents, 1);
  if (ev.phase === 2) renderAgentChips('p2-agents', ev.agents, 2);
  if (ev.phase === 3) {
    renderAgentChips('p3-agents', ev.agents, 3);
    setPhaseStatus('p3', '<span class="spinner"></span> Debating', 'text-indigo-400');
  }
  if (ev.phase === 4) {
    renderAgentChips('p4-agents', ev.agents, 4);
    setPhaseStatus('p4', '<span class="spinner"></span> Synthesising', 'text-indigo-400');
    document.getElementById('pm-output').innerHTML =
      '<p class="text-xs text-gray-500">Portfolio Manager thinking…</p>';
  }
}

// ── agent_log: agent about to be dispatched ───────────────────────────────────
function onAgentLog(ev) {
  const state = agentExpandState[ev.agent];
  if (!state) return;
  state.model = ev.model;
  state.elapsedStart = Date.now();

  // If expand panel is open, update it
  if (state.expanded) renderAgentDetail(ev.agent, ev.phase);

  // Start elapsed timer
  if (state.timerId) clearInterval(state.timerId);
  state.timerId = setInterval(() => {
    const detailEl = document.getElementById('detail-' + ev.agent);
    if (detailEl && state.status === 'running') {
      const secs = Math.floor((Date.now() - state.elapsedStart) / 1000);
      const et = detailEl.querySelector('.elapsed-timer');
      if (et) et.textContent = secs + 's';
    }
  }, 1000);
}

// ── onAgentComplete ───────────────────────────────────────────────────────────
function onAgentComplete(ev) {
  const chip = document.getElementById('chip-' + ev.agent);
  if (!chip) return;

  // Update chip appearance
  chip.classList.remove('running');
  chip.classList.add(ev.status === 'failed' ? 'failed' : 'complete');

  const dot = chip.querySelector('.chip-dot');
  if (dot) { dot.className = 'chip-dot ' + (ev.status === 'failed' ? 'failed' : 'done'); }

  // Store result in expand state
  const state = agentExpandState[ev.agent];
  if (state) {
    state.status = ev.status === 'failed' ? 'failed' : 'complete';
    if (state.timerId) { clearInterval(state.timerId); state.timerId = null; }
    state.result = ev;
    if (state.expanded) renderAgentDetail(ev.agent, ev.phase);
  }

  // Update chip label to show score
  const nameSpan = chip.querySelector('.chip-label');
  if (nameSpan && ev.score != null) {
    nameSpan.textContent = fmtAgentName(ev.agent) + ' · ' + ev.score;
  }
}

function onPhaseComplete(ev) {
  setPhaseStatus('p' + ev.phase, 'Complete', 'text-green-400');
}

// ── Debate handlers ───────────────────────────────────────────────────────────
function onDebateRound(ev) {
  const feed = document.getElementById('debate-feed');
  const gap = ev.gap;
  const gapColor = gap <= 2 ? 'text-green-400' : gap <= 4 ? 'text-yellow-400' : 'text-red-400';

  const card = document.createElement('div');
  card.className = 'debate-round';
  card.innerHTML = `
    <div class="round-header">
      <span>Round ${ev.round}</span>
      <span class="${gapColor}">Gap: ${gap}</span>
    </div>
    <div class="bull-side">
      <span class="font-semibold text-xs">BULL</span>
      <div class="text-gray-300 mt-1">${escHtml(ev.bull_argument || '')}</div>
    </div>
    <div class="bear-side mt-2">
      <span class="font-semibold text-xs">BEAR</span>
      <div class="text-gray-300 mt-1">${escHtml(ev.bear_argument || '')}</div>
    </div>
    <div class="conviction-row">
      <span class="text-green-400">Bull conviction: ${ev.bull_conviction}/10</span>
      <span class="text-red-400">Bear conviction: ${ev.bear_conviction}/10</span>
    </div>
  `;
  feed.appendChild(card);
  feed.scrollTop = feed.scrollHeight;
}

function onDebateComplete(ev) {
  const summary = document.getElementById('debate-summary');
  summary.classList.remove('hidden');
  const label = ev.contested
    ? '<span class="text-yellow-400 font-semibold">⚠ Contested</span> — no consensus after 4 rounds'
    : '<span class="text-green-400 font-semibold">Consensus reached</span>';
  summary.innerHTML = `${label} &nbsp;|&nbsp; ${ev.rounds} rounds &nbsp;|&nbsp; Bull: ${ev.bull_score} · Bear: ${ev.bear_score}`;
  setPhaseStatus('p3', ev.contested ? 'Contested' : 'Consensus', ev.contested ? 'text-yellow-400' : 'text-green-400');

  // Mark bull/bear chips as complete
  ['bull', 'bear'].forEach(name => {
    const chip = document.getElementById('chip-' + name);
    if (chip) {
      chip.classList.remove('running');
      chip.classList.add('complete');
      const dot = chip.querySelector('.chip-dot');
      if (dot) dot.className = 'chip-dot done';
    }
    const state = agentExpandState[name];
    if (state) { state.status = 'complete'; }
  });
}

// ── Verdict ───────────────────────────────────────────────────────────────────
function onVerdict(ev) {
  setPhaseStatus('p4', 'Complete', 'text-green-400');

  document.getElementById('pm-output').innerHTML =
    `<p class="text-xs text-gray-400">${escHtml(ev.reasoning || '')}</p>`;

  const card = document.getElementById('verdict-card');
  card.classList.remove('hidden');
  card.classList.add(ev.verdict === 'WATCHLIST' ? 'verdict-watchlist' : 'verdict-avoid');

  document.getElementById('verdict-label').textContent = ev.verdict;
  document.getElementById('verdict-label').className =
    'text-3xl font-bold ' + (ev.verdict === 'WATCHLIST' ? 'text-green-400' : 'text-red-400');

  const tier = (ev.tier || '').toLowerCase();
  document.getElementById('verdict-tier').textContent =
    SCORE_LABELS[ev.score] + (tier ? ' · ' + tier : '');

  const scoreEl = document.getElementById('verdict-score');
  scoreEl.innerHTML = `<div class="score-badge score-${ev.score}">${ev.score}</div>`;

  document.getElementById('verdict-entry').textContent =
    ev.entry_low && ev.entry_high
      ? `$${fmtNum(ev.entry_low)} – $${fmtNum(ev.entry_high)}`
      : '—';
  document.getElementById('verdict-stop').textContent   = ev.stop_loss   ? '$' + fmtNum(ev.stop_loss)   : '—';
  document.getElementById('verdict-target').textContent = ev.target_price ? '$' + fmtNum(ev.target_price) : '—';

  if (ev.expected_returns) renderReturnsTable(ev.expected_returns);

  document.getElementById('verdict-reasoning').textContent = ev.reasoning || '';

  if (ev.key_risks && ev.key_risks.length) {
    document.getElementById('verdict-risks').innerHTML =
      '<div class="text-xs text-gray-500 mb-1">Key Risks</div>' +
      ev.key_risks.map(r => `<div class="text-xs text-red-300 flex gap-1"><span>▸</span><span>${escHtml(r)}</span></div>`).join('');
  }

  if (ev.key_catalysts && ev.key_catalysts.length) {
    document.getElementById('verdict-catalysts').innerHTML =
      '<div class="text-xs text-gray-500 mb-1 mt-2">Key Catalysts</div>' +
      ev.key_catalysts.map(c => `<div class="text-xs text-green-300 flex gap-1"><span>▸</span><span>${escHtml(c)}</span></div>`).join('');
  }

  if (ev.contested) {
    document.getElementById('verdict-contested').classList.remove('hidden');
  }
}

function renderReturnsTable(returns) {
  const el = document.getElementById('verdict-returns');
  if (!returns || typeof returns !== 'object') return;
  const horizons = Object.keys(returns);
  if (!horizons.length) return;

  let html = '<table class="returns-table"><thead><tr><th>Horizon</th><th>Bear</th><th>Base</th><th>Bull</th></tr></thead><tbody>';
  horizons.forEach(h => {
    const r = returns[h];
    const bear = r.bear != null ? r.bear + '%' : '—';
    const base = r.base != null ? r.base + '%' : (r.expected != null ? r.expected + '%' : '—');
    const bull = r.bull != null ? r.bull + '%' : '—';
    html += `<tr><td class="text-gray-400">${h}</td><td class="text-red-400">${bear}</td><td class="text-gray-200">${base}</td><td class="text-green-400">${bull}</td></tr>`;
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

// ── Complete / Abort ──────────────────────────────────────────────────────────
function onComplete(ev) {
  const badge = document.getElementById('run-status-badge');
  badge.textContent = 'Complete';
  badge.className = 'text-xs px-3 py-1 rounded-full bg-green-900 text-green-300';
}

function onAbort(ev) {
  const badge = document.getElementById('run-status-badge');
  badge.textContent = 'Aborted';
  badge.className = 'text-xs px-3 py-1 rounded-full bg-red-900 text-red-300';

  const card = document.getElementById('abort-card');
  card.classList.remove('hidden');
  document.getElementById('abort-reason').textContent =
    ev.reason + (ev.agents ? ' (' + ev.agents.join(', ') + ')' : '');
}

function showError(msg) {
  const badge = document.getElementById('run-status-badge');
  if (badge) {
    badge.textContent = 'Error';
    badge.className = 'text-xs px-3 py-1 rounded-full bg-red-900 text-red-300';
  }
  console.error('[hf] Error:', msg);
}

function onStreamDone() {
  // no-op — start button is in the modal now
}

// ── Agent chips ───────────────────────────────────────────────────────────────
function renderAgentChips(containerId, agents, phase) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  agents.forEach(name => {
    // Init expand state
    agentExpandState[name] = { expanded: false, status: 'running', result: null, model: null, elapsedStart: null, timerId: null, phase };

    const btn = document.createElement('button');
    btn.className = 'agent-chip running';
    btn.id = 'chip-' + name;
    btn.dataset.agent = name;
    btn.dataset.phase = phase;
    btn.innerHTML = `<span class="chip-dot running"></span><span class="chip-label">${fmtAgentName(name)}</span>`;
    btn.addEventListener('click', () => toggleAgentExpand(name, phase));
    el.appendChild(btn);
  });
}

// ── Agent expand ──────────────────────────────────────────────────────────────
function toggleAgentExpand(agentName, phase) {
  const state = agentExpandState[agentName];
  if (!state) return;

  state.expanded = !state.expanded;

  const chip = document.getElementById('chip-' + agentName);
  if (chip) chip.classList.toggle('expanded', state.expanded);

  const expandArea = document.getElementById('p' + phase + '-expand');
  if (!expandArea) return;

  const existingDetail = document.getElementById('detail-' + agentName);

  if (!state.expanded) {
    if (existingDetail) existingDetail.remove();
    return;
  }

  // Insert detail panel
  if (!existingDetail) {
    const div = document.createElement('div');
    div.id = 'detail-' + agentName;
    div.className = 'agent-detail';
    expandArea.appendChild(div);
  }
  renderAgentDetail(agentName, phase);
}

function renderAgentDetail(agentName, phase) {
  const state = agentExpandState[agentName];
  const detailEl = document.getElementById('detail-' + agentName);
  if (!detailEl || !state) return;

  const displayName = fmtAgentName(agentName);

  if (state.status === 'running') {
    const elapsed = state.elapsedStart ? Math.floor((Date.now() - state.elapsedStart) / 1000) : 0;
    const modelStr = state.model ? escHtml(state.model) : '…';
    detailEl.innerHTML = `
      <div class="detail-header">
        <span class="detail-name">${escHtml(displayName)}</span>
        <span class="detail-pill pill-running">● Running</span>
      </div>
      <div class="detail-body">
        <div class="running-log">
          <div class="log-line"><span class="log-ts">00:00</span><span class="log-msg">Dispatching to <span class="log-hl">${modelStr}</span>…</span></div>
          <div class="log-line"><span class="log-ts"><span class="elapsed-timer">${elapsed}s</span></span><span class="log-msg">Waiting for response <span class="log-cursor"></span></span></div>
        </div>
      </div>`;
  } else {
    const r = state.result || {};
    const score = r.score != null ? r.score : '—';
    const conf  = r.data_confidence || '';
    const dur   = r.duration_ms != null ? (r.duration_ms / 1000).toFixed(1) + 's' : '';
    const confClass = conf === 'full' ? 'conf-full' : conf === 'partial' ? 'conf-partial' : 'conf-minimal';
    const pillClass = state.status === 'failed' ? 'pill-failed' : 'pill-done';
    const pillText  = state.status === 'failed' ? '✗ Failed' : '✓ Complete';

    const bull = Array.isArray(r.bull_points) ? r.bull_points : [];
    const bear = Array.isArray(r.bear_points) ? r.bear_points : [];
    const missing = Array.isArray(r.missing_fields) ? r.missing_fields : [];

    const bullHtml = bull.map(p => `<div class="point-item bull">${escHtml(p)}</div>`).join('');
    const bearHtml = bear.map(p => `<div class="point-item bear">${escHtml(p)}</div>`).join('');
    const missingHtml = missing.length ? `
      <div class="detail-missing">
        <div class="missing-lbl">⚠ Missing fields</div>
        ${missing.map(m => `<div class="missing-item">${escHtml(m)}</div>`).join('')}
      </div>` : '';

    const pointsHtml = (bull.length || bear.length) ? `
      <div class="detail-points">
        <div><div class="points-label bull">Bull</div>${bullHtml}</div>
        <div><div class="points-label bear">Bear</div>${bearHtml}</div>
      </div>` : '';

    detailEl.innerHTML = `
      <div class="detail-header">
        <span class="detail-name">${escHtml(displayName)}</span>
        <span class="detail-pill ${pillClass}">${pillText}</span>
      </div>
      <div class="detail-body">
        <div class="detail-score-row">
          <div>
            <div class="detail-score-num">${score}<span style="font-size:0.7rem;color:#6b7280;font-weight:400"> / 10</span></div>
            <div class="detail-score-lbl">Score</div>
          </div>
          ${conf ? `<div><span class="conf-badge ${confClass}">${conf}</span><div class="detail-score-lbl" style="margin-top:3px">Data quality</div></div>` : ''}
          ${dur ? `<div class="detail-dur">${dur}</div>` : ''}
        </div>
        ${r.summary ? `<div class="detail-summary">${escHtml(r.summary)}</div>` : ''}
        ${pointsHtml}
        ${missingHtml}
      </div>`;
  }
}

// ── Upload / Resume ───────────────────────────────────────────────────────────
function handleDrop(event) {
  event.preventDefault();
  uploadFiles(event.dataTransfer.files);
}

function handleFileSelect(event) {
  uploadFiles(event.target.files);
}

function uploadFiles(files) {
  if (!currentRunId) return;
  const ticker = document.getElementById('run-ticker').textContent;
  const promises = Array.from(files).map(file => {
    const form = new FormData();
    form.append('file', file);
    return fetch(`/upload/${ticker}/${currentRunId}`, { method: 'POST', body: form });
  });
  Promise.all(promises).then(() => {
    document.getElementById('resume-btn').disabled = false;
  });
}

function resumeRun() {
  if (!currentRunId) return;
  document.getElementById('upload-zone').classList.add('hidden');
  document.getElementById('run-status-badge').textContent = 'Resuming';

  fetch(`/resume/${currentRunId}`, { method: 'POST' }).then(res => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    function pump() {
      reader.read().then(({ done, value }) => {
        if (done) { onStreamDone(); return; }
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        lines.forEach(line => {
          if (line.startsWith('data: ')) {
            try { handleEvent(JSON.parse(line.slice(6))); } catch (_) {}
          }
        });
        pump();
      });
    }
    pump();
  });
}

// ── Watchlist ─────────────────────────────────────────────────────────────────
function loadWatchlist() {
  fetch('/watchlist').then(r => r.json()).then(entries => {
    const el = document.getElementById('watchlist-table');
    if (!entries.length) {
      el.innerHTML = '<p class="text-gray-500 text-sm text-center py-8">No watchlist entries yet.</p>';
      return;
    }
    let html = `<table class="data-table">
      <thead><tr>
        <th>Ticker</th><th>Score</th><th>Tier</th>
        <th>Entry Zone</th><th>Stop</th><th>Target</th>
        <th>Added</th><th>Status</th>
      </tr></thead><tbody>`;
    entries.forEach(e => {
      const entry = e.entry_low && e.entry_high ? `$${fmtNum(e.entry_low)}–$${fmtNum(e.entry_high)}` : '—';
      const contested = e.contested ? ' <span class="text-yellow-400">⚠</span>' : '';
      html += `<tr>
        <td class="font-bold tracking-wider">${escHtml(e.ticker)}${contested}</td>
        <td><span class="score-badge score-${e.score || 3}" style="width:1.8rem;height:1.8rem;font-size:0.8rem">${e.score || '?'}</span></td>
        <td class="text-gray-400">${escHtml(e.tier || '—')}</td>
        <td>${entry}</td>
        <td class="text-red-400">${e.stop_loss ? '$' + fmtNum(e.stop_loss) : '—'}</td>
        <td class="text-green-400">${e.target_price ? '$' + fmtNum(e.target_price) : '—'}</td>
        <td class="text-gray-500">${e.added_date || '—'}</td>
        <td><span class="text-xs px-2 py-0.5 rounded-full ${statusBadge(e.status)}">${e.status}</span></td>
      </tr>`;
    });
    html += '</tbody></table>';
    el.innerHTML = html;
  });
}

// ── Runs ──────────────────────────────────────────────────────────────────────
function loadRuns() {
  fetch('/runs').then(r => r.json()).then(runs => {
    const el = document.getElementById('runs-table');
    if (!runs.length) {
      el.innerHTML = '<p class="text-gray-500 text-sm text-center py-8">No runs yet.</p>';
      return;
    }
    let html = `<table class="data-table">
      <thead><tr>
        <th>ID</th><th>Ticker</th><th>Date</th>
        <th>Status</th><th>Verdict</th><th>Score</th>
      </tr></thead><tbody>`;
    runs.forEach(r => {
      const verdictCls = r.verdict === 'watchlist' ? 'text-green-400' : r.verdict === 'avoid' ? 'text-red-400' : 'text-gray-400';
      html += `<tr>
        <td class="text-gray-500">#${r.id}</td>
        <td class="font-bold tracking-wider">${escHtml(r.ticker)}</td>
        <td class="text-gray-500">${r.run_date || '—'}</td>
        <td><span class="text-xs px-2 py-0.5 rounded-full ${statusBadge(r.status)}">${r.status}</span></td>
        <td class="${verdictCls} font-semibold">${(r.verdict || '—').toUpperCase()}</td>
        <td>${r.score != null ? `<span class="score-badge score-${r.score}" style="width:1.8rem;height:1.8rem;font-size:0.8rem">${r.score}</span>` : '—'}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    el.innerHTML = html;
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setPhaseStatus(key, html, cls) {
  const el = document.getElementById(key + '-status');
  if (!el) return;
  el.innerHTML = html;
  el.className = 'phase-status text-xs ' + (cls || 'text-gray-500');
}

function fmtAgentName(name) {
  const map = {
    fundamental: 'Fundamental',
    technical: 'Technical',
    sentiment: 'Sentiment',
    macro: 'Macro',
    earnings_reviewer: 'Earnings',
    risk_manager: 'Risk Mgr',
    thesis_validator: 'Thesis',
    financial_modeler: 'Fin. Model',
    portfolio_manager: 'PM',
    bull: 'Bull',
    bear: 'Bear',
  };
  return map[name] || name;
}

function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 });
}

function escHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function statusBadge(status) {
  const m = {
    complete: 'bg-green-900 text-green-300',
    watching: 'bg-indigo-900 text-indigo-300',
    running: 'bg-yellow-900 text-yellow-300',
    failed: 'bg-red-900 text-red-300',
    paused: 'bg-orange-900 text-orange-300',
    contested: 'bg-yellow-900 text-yellow-300',
    avoid: 'bg-red-900 text-red-300',
    promoted: 'bg-blue-900 text-blue-300',
    dismissed: 'bg-gray-800 text-gray-500',
  };
  return m[status] || 'bg-gray-800 text-gray-400';
}

// ── Shutdown ──────────────────────────────────────────────────────────────────
async function stopServer() {
  const btn = document.getElementById('stop-btn');
  btn.disabled = true;
  btn.textContent = 'Stopping…';
  try {
    await fetch('/shutdown', { method: 'POST' });
    btn.textContent = 'Server stopped — you can close this tab.';
  } catch {
    btn.textContent = 'Server stopped — you can close this tab.';
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Keyboard shortcut: Escape closes modal
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  updateCostEstimate();
  showTab('analyse');
});
