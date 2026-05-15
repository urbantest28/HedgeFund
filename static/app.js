/* HedgeFund Analyser — frontend JS */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let currentRunId = null;
let activeSource = null;

const SCORE_LABELS = { 1: 'Strong Buy', 2: 'Buy', 3: 'Neutral', 4: 'Sell', 5: 'Strong Sell' };

// ── Tab routing ───────────────────────────────────────────────────────────────
function showTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('pane-' + name).classList.remove('hidden');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'watchlist') loadWatchlist();
  if (name === 'runs') loadRuns();
}

// ── Analysis ──────────────────────────────────────────────────────────────────
function startAnalysis() {
  const ticker = document.getElementById('ticker-input').value.trim().toUpperCase();
  if (!ticker) return;

  resetProgressPanel(ticker);
  document.getElementById('progress-panel').classList.remove('hidden');
  document.getElementById('analyse-btn').disabled = true;

  if (activeSource) activeSource.close();

  fetch('/analyse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
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
    document.getElementById('analyse-btn').disabled = false;
  });
}

function resetProgressPanel(ticker) {
  currentRunId = null;
  document.getElementById('run-ticker').textContent = ticker;
  document.getElementById('run-id-badge').textContent = 'run #–';
  document.getElementById('run-status-badge').textContent = 'Running';
  document.getElementById('run-status-badge').className =
    'text-xs px-3 py-1 rounded-full bg-yellow-900 text-yellow-300';

  ['p1','p2','p3','p4'].forEach(p => {
    const s = document.getElementById(p + '-status');
    if (s) { s.textContent = 'Waiting'; s.className = 'phase-status text-xs text-gray-500'; }
  });
  document.getElementById('p1-agents').innerHTML = '';
  document.getElementById('p2-agents').innerHTML = '';
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

// ── Phase handlers ────────────────────────────────────────────────────────────
function onPhaseStart(ev) {
  const key = 'p' + ev.phase;
  setPhaseStatus(key, '<span class="spinner"></span> Running', 'text-indigo-400');

  if (ev.phase === 1) renderAgentChips('p1-agents', ev.agents);
  if (ev.phase === 2) renderAgentChips('p2-agents', ev.agents);
  if (ev.phase === 3) setPhaseStatus('p3', '<span class="spinner"></span> Debating', 'text-indigo-400');
  if (ev.phase === 4) {
    setPhaseStatus('p4', '<span class="spinner"></span> Synthesising', 'text-indigo-400');
    document.getElementById('pm-output').innerHTML =
      '<p class="text-xs text-gray-500">Portfolio Manager thinking…</p>';
  }
}

function onAgentComplete(ev) {
  const chip = document.getElementById('chip-' + ev.agent);
  if (!chip) return;

  chip.classList.remove('running');
  chip.classList.add(ev.status === 'failed' ? 'failed' : 'complete');

  const scoreEl = chip.querySelector('.chip-score');
  const confEl  = chip.querySelector('.chip-conf');
  if (scoreEl) scoreEl.textContent = ev.score != null ? ev.score + '/10' : '—';
  if (confEl) {
    confEl.textContent = ev.data_confidence || '';
    confEl.className = 'chip-conf ' + (ev.data_confidence || '');
  }
}

function onPhaseComplete(ev) {
  const key = 'p' + ev.phase;
  setPhaseStatus(key, 'Complete', 'text-green-400');
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

  if (ev.expected_returns) {
    renderReturnsTable(ev.expected_returns);
  }

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
  document.getElementById('analyse-btn').disabled = false;
}

function onAbort(ev) {
  const badge = document.getElementById('run-status-badge');
  badge.textContent = 'Aborted';
  badge.className = 'text-xs px-3 py-1 rounded-full bg-red-900 text-red-300';

  const card = document.getElementById('abort-card');
  card.classList.remove('hidden');
  document.getElementById('abort-reason').textContent =
    ev.reason + (ev.agents ? ' (' + ev.agents.join(', ') + ')' : '');

  document.getElementById('analyse-btn').disabled = false;
}

function showError(msg) {
  const badge = document.getElementById('run-status-badge');
  if (badge) {
    badge.textContent = 'Error';
    badge.className = 'text-xs px-3 py-1 rounded-full bg-red-900 text-red-300';
  }
  console.error('[hf] Error:', msg);
  document.getElementById('analyse-btn').disabled = false;
}

function onStreamDone() {
  document.getElementById('analyse-btn').disabled = false;
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
      const scoreCls = 'score-' + (e.score || 3);
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
function renderAgentChips(containerId, agents) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  agents.forEach(name => {
    const chip = document.createElement('div');
    chip.className = 'agent-chip running';
    chip.id = 'chip-' + name;
    chip.innerHTML = `
      <span class="chip-name">${fmtAgentName(name)}</span>
      <span class="chip-score">…</span>
      <span class="chip-conf"></span>
    `;
    el.appendChild(chip);
  });
}

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
  const input = document.getElementById('ticker-input');
  input.addEventListener('keydown', e => { if (e.key === 'Enter') startAnalysis(); });
  showTab('analyse');
});
