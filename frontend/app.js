/* YouTube Fact Checker — Frontend Logic */

let currentTaskId = null;
let pollInterval = null;
let elapsedInterval = null;
let elapsedStart = null;
let allClaims = [];
let pollFailures = 0;
const MAX_POLL_FAILURES = 5;
let pollTimeout = null;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;
let lastProgressPct = 0;

// --- Submit ---

async function submitVideo() {
  stopPolling();

  const input = document.getElementById('url-input');
  const url = input.value.trim();
  const errorEl = document.getElementById('input-error');
  const btn = document.getElementById('check-btn');

  errorEl.textContent = '';

  if (!url || !YT_URL_REGEX.test(url)) {
    errorEl.textContent = 'Please enter a valid YouTube URL.';
    return;
  }

  // Disable button
  btn.disabled = true;
  btn.querySelector('.btn-text').style.display = 'none';
  btn.querySelector('.btn-loading').style.display = 'inline';

  const submitController = new AbortController();
  const submitTimeout = setTimeout(() => submitController.abort(), 30000);

  try {
    const resp = await fetch('/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ youtube_url: url }),
      signal: submitController.signal,
    });

    if (!resp.ok) {
      let message = `Request failed (${resp.status})`;
      try {
        const ct = resp.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          const data = await resp.json();
          message = data.detail || message;
        }
      } catch (_) {}
      throw new Error(message);
    }

    let data;
    try {
      data = await resp.json();
    } catch (_) {
      throw new Error('Invalid response from server');
    }
    currentTaskId = data.task_id;

    if (data.status === 'completed') {
      renderResults(data.data);
      resetButton();
      return;
    }

    if (data.status === 'queued') {
      showSection('queued');
      resetButton();
      return;
    }

    // Show loading
    showSection('loading');
    smoothScroll(document.getElementById('loading-section'));
    startPolling();

  } catch (err) {
    errorEl.textContent = err.message;
    resetButton();
    return;
  } finally {
    clearTimeout(submitTimeout);
  }
}

// --- Polling ---

function startPolling() {
  if (pollTimeout) clearTimeout(pollTimeout);
  if (pollInterval) clearTimeout(pollInterval);
  lastProgressPct = 0;
  updateProgress('Starting analysis...', 10);
  startElapsedTimer();
  pollFailures = 0;

  pollTimeout = setTimeout(() => {
    stopPolling();
    showErrorHtml('Analysis is taking too long. The video may still be processing — check the <a href="/videos">Videos page</a> later.');
  }, POLL_TIMEOUT_MS);

  schedulePoll();
}

async function schedulePoll() {
  pollInterval = setTimeout(async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      const resp = await fetch(`/api/check/${currentTaskId}`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (!resp.ok) {
        if (resp.status >= 400 && resp.status < 500) {
          stopPolling();
          showError(resp.status === 404 ? 'Analysis task not found.' : `Server error (${resp.status}).`);
          return;
        }
        throw new Error('Polling failed');
      }

      let data;
      try { data = await resp.json(); } catch (_) { throw new Error('Invalid JSON'); }
      if (!data || typeof data.status !== 'string') throw new Error('Unexpected response');
      pollFailures = 0;

      if (data.status === 'processing') {
        updateProgress(data.progress || 'Processing...', estimateProgress(data.progress));
      } else if (data.status === 'completed') {
        stopPolling();
        renderResults(data.data);
        return;
      } else if (data.status === 'failed') {
        stopPolling();
        showError(data.error || 'An error occurred during analysis.');
        return;
      } else if (data.status === 'queued') {
        stopPolling();
        document.title = 'YouTube Fact Checker';
        showSection('queued');
        return;
      }
    } catch (err) {
      pollFailures++;
      if (pollFailures >= MAX_POLL_FAILURES) {
        stopPolling();
        showError('Connection lost. Please try again.');
        return;
      }
    }
    if (pollInterval !== null) schedulePoll();
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearTimeout(pollInterval);
    pollInterval = null;
  }
  if (pollTimeout) {
    clearTimeout(pollTimeout);
    pollTimeout = null;
  }
  stopElapsedTimer();
  resetButton();
}

function formatElapsed(ms) {
  const totalSec = Math.round(ms / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}m ${s}s`;
}

function startElapsedTimer() {
  if (elapsedInterval) clearInterval(elapsedInterval);
  elapsedStart = Date.now();
  const el = document.getElementById('loading-elapsed');
  if (el) el.textContent = 'Elapsed: 0s';
  elapsedInterval = setInterval(() => {
    if (el) el.textContent = `Elapsed: ${formatElapsed(Date.now() - elapsedStart)}`;
  }, 1000);
}

function stopElapsedTimer() {
  if (elapsedInterval) {
    clearInterval(elapsedInterval);
    elapsedInterval = null;
  }
}

function estimateProgress(progressText) {
  if (!progressText) return 15;
  if (progressText.includes('Starting')) return 5;
  if (progressText.includes('transcript')) return 20;
  if (progressText.includes('Analyzing')) return 35;
  if (progressText.includes('Fact-checking')) {
    const match = progressText.match(/(\d+)\/(\d+)/);
    if (match) {
      const total = parseInt(match[2]);
      if (total > 0) {
        const pct = 40 + (parseInt(match[1]) / total) * 55;
        return Math.min(95, Math.round(pct));
      }
    }
    return 50;
  }
  if (progressText.includes('Done')) return 100;
  return 25;
}

function updateProgress(text, pct) {
  pct = Math.max(pct, lastProgressPct);
  lastProgressPct = pct;
  document.getElementById('loading-status').textContent = text;
  document.getElementById('progress-fill').style.width = pct + '%';
  const bar = document.querySelector('.progress-bar[role="progressbar"]');
  if (bar) bar.setAttribute('aria-valuenow', pct);
  document.title = `${pct}% — ${text} | YouTube Fact Checker`;
}

// --- Render Results ---

function renderResults(data) {
  allClaims = (data.claims || []).map((c, i) => ({...c, _num: i + 1}));

  // Video info
  const titleEl = document.getElementById('video-title');
  titleEl.textContent = data.video_title || 'Untitled Video';
  titleEl.dataset.videoId = data.video_id || '';

  document.getElementById('video-duration').textContent = `${formatTimestamp(data.video_duration_seconds)} duration`;
  document.getElementById('processing-time').textContent = `Analyzed in ${data.processing_time_seconds}s`;

  // Overall score
  const score = data.overall_truth_percentage;
  document.getElementById('summary-text').textContent = data.summary || '';

  // Animate score ring
  const sc = scoreColor(score);
  const circle = document.getElementById('score-circle');
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (score / 100) * circumference;
  circle.setAttribute('stroke-dasharray', circumference);
  circle.style.strokeDashoffset = offset;
  circle.style.stroke = sc;

  const ringSvg = circle.closest('svg');
  if (ringSvg) ringSvg.setAttribute('aria-label', `Accuracy score: ${score}%`);

  // Color & animate score counter
  document.getElementById('score-value').style.color = sc;
  animateCounter('score-value', 0, score, 800);

  // Render breakdown stats
  renderBreakdownBar(allClaims);

  // Render claims
  setActiveFilter('all');
  renderClaimsList(allClaims);

  // Update claims heading and filter button counts
  const claimsHeading = document.getElementById('claims-heading');
  if (claimsHeading) claimsHeading.textContent = `Claims (${allClaims.length})`;
  updateFilterCounts(allClaims);

  // Show "View full report" link
  const reportLink = document.getElementById('view-report-link');
  if (data.video_id) {
    reportLink.href = `/video/${data.video_id}`;
    reportLink.style.display = 'inline-block';
  } else {
    reportLink.style.display = 'none';
  }

  document.title = `${data.video_title || 'Results'} — YouTube Fact Checker`;
  showSection('results');
  smoothScroll(document.getElementById('results-section'));
}

function renderClaimsList(claims) {
  const container = document.getElementById('claims-list');

  if (claims.length === 0) {
    container.innerHTML = '<div class="empty-state">No claims found.</div>';
    return;
  }

  const videoId = document.getElementById('video-title').dataset.videoId || '';
  container.innerHTML = claims.map((c, i) =>
    buildClaimCardHtml(c, i, { videoId, sourcesLimit: 3 })
  ).join('');

  addCardClickListeners('claims-list');
}

function filterClaims(filter) {
  setActiveFilter(filter);

  const filtered = filter === 'all'
    ? allClaims
    : filter === 'fact'
      ? allClaims.filter(c => c.category === 'fact' || c.category === 'unclear')
      : allClaims.filter(c => c.category === filter);

  renderClaimsList(filtered);

  const btn = document.getElementById('toggle-all-btn');
  if (btn) btn.textContent = 'Expand all';
}

function cancelAnalysis() {
  stopPolling();
  currentTaskId = null;
  document.title = 'YouTube Fact Checker';
  showSection(null);
  resetButton();
}

function showSection(name) {
  ['loading', 'error', 'results', 'queued'].forEach(s => {
    document.getElementById(`${s}-section`).style.display = s === name ? 'block' : 'none';
  });
  const howSection = document.querySelector('.how-it-works');
  if (howSection) howSection.style.display = name ? 'none' : '';
}

function showError(message) {
  document.getElementById('error-message').textContent = message;
  document.title = 'YouTube Fact Checker';
  showSection('error');
  smoothScroll(document.getElementById('error-section'));
  resetButton();
}

function showErrorHtml(html) {
  document.getElementById('error-message').innerHTML = html;
  document.title = 'YouTube Fact Checker';
  showSection('error');
  smoothScroll(document.getElementById('error-section'));
  resetButton();
}

function retryVideo() {
  const url = document.getElementById('url-input').value.trim();
  if (url) {
    showSection(null);
    submitVideo();
  } else {
    resetUI();
  }
}

function resetButton() {
  const btn = document.getElementById('check-btn');
  btn.disabled = false;
  btn.querySelector('.btn-text').style.display = 'inline';
  btn.querySelector('.btn-loading').style.display = 'none';
}

function resetUI() {
  stopPolling();
  document.title = 'YouTube Fact Checker';
  showSection(null);
  document.getElementById('url-input').value = '';
  document.getElementById('input-error').textContent = '';
  _previewEl.style.display = 'none';
  document.getElementById('view-report-link').style.display = 'none';
  resetButton();
  allClaims = [];
}

// Button & action listeners
document.getElementById('check-btn').addEventListener('click', submitVideo);
document.getElementById('cancel-btn').addEventListener('click', cancelAnalysis);

document.addEventListener('click', (e) => {
  if (e.target.closest('[data-action="reset-ui"]')) { resetUI(); return; }
  if (e.target.closest('[data-action="retry-video"]')) { retryVideo(); return; }
  const filterBtn = e.target.closest('.filter-btn[data-filter]');
  if (filterBtn) { filterClaims(filterBtn.dataset.filter); return; }
  if (e.target.closest('#toggle-all-btn')) { toggleAllClaims('claims-list'); }
});

// Enter key support
document.getElementById('url-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') submitVideo();
});

// URL preview on input (debounced)
let _previewTimer;
document.getElementById('url-input').addEventListener('input', () => {
  clearTimeout(_previewTimer);
  _previewTimer = setTimeout(showUrlPreview, 200);
});
document.getElementById('url-input').addEventListener('paste', () => {
  clearTimeout(_previewTimer);
  setTimeout(showUrlPreview, 0);
});

document.getElementById('url-input').focus();

document.addEventListener('keydown', (e) => {
  if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)) return;
    e.preventDefault();
    document.getElementById('url-input').focus();
  }
  if (e.key === 'Escape') {
    if (pollInterval) {
      cancelAnalysis();
    } else {
      if (!collapseAllCards('claims-list')) {
        const input = document.getElementById('url-input');
        if (input.value) {
          input.value = '';
          _previewEl.style.display = 'none';
          document.getElementById('input-error').textContent = '';
          input.focus();
        } else {
          input.blur();
        }
      }
    }
  }
});

// Load site stats
(async function loadStats() {
  const statsController = new AbortController();
  setTimeout(() => statsController.abort(), 5000);
  try {
    const resp = await fetch('/api/stats', { signal: statsController.signal });
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.video_count > 0) {
      const vEl = document.getElementById('stat-videos');
      const cEl = document.getElementById('stat-claims');
      const chEl = document.getElementById('stat-channels');
      const container = document.getElementById('site-stats');
      if (vEl) vEl.textContent = data.video_count;
      if (cEl) cEl.textContent = data.claim_count;
      if (chEl) chEl.textContent = data.channel_count;
      if (container) container.style.display = '';
    }
  } catch (_) {}
})();

const _previewThumb = document.getElementById('preview-thumb');
const _previewEl = document.getElementById('url-preview');
if (_previewThumb) _previewThumb.addEventListener('error', () => { _previewEl.style.display = 'none'; });

function showUrlPreview() {
  const url = document.getElementById('url-input').value.trim();
  const match = url.match(YT_URL_REGEX);

  if (match) {
    const videoId = match[1];
    _previewThumb.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    document.getElementById('preview-id').textContent = `Video ID: ${videoId}`;
    _previewEl.style.display = 'flex';
  } else {
    _previewEl.style.display = 'none';
  }
}
