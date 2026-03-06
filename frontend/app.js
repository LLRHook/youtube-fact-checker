/* YouTube Fact Checker — Frontend Logic */

let currentTaskId = null;
let pollInterval = null;
let allClaims = [];

// --- Submit ---

async function submitVideo() {
  const input = document.getElementById('url-input');
  const url = input.value.trim();
  const errorEl = document.getElementById('input-error');
  const btn = document.getElementById('check-btn');

  errorEl.textContent = '';

  // Validate
  const ytRegex = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/;
  if (!url || !ytRegex.test(url)) {
    errorEl.textContent = 'Please enter a valid YouTube URL.';
    return;
  }

  // Disable button
  btn.disabled = true;
  btn.querySelector('.btn-text').style.display = 'none';
  btn.querySelector('.btn-loading').style.display = 'inline';

  try {
    const resp = await fetch('/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ youtube_url: url }),
    });

    if (!resp.ok) {
      const data = await resp.json();
      throw new Error(data.detail || 'Failed to submit video.');
    }

    const data = await resp.json();
    currentTaskId = data.task_id;

    // Show loading
    showSection('loading');
    startPolling();

  } catch (err) {
    errorEl.textContent = err.message;
    resetButton();
  }
}

// --- Polling ---

function startPolling() {
  updateProgress('Starting analysis...', 10);

  pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/check/${currentTaskId}`);
      if (!resp.ok) throw new Error('Polling failed');

      const data = await resp.json();

      if (data.status === 'processing') {
        updateProgress(data.progress || 'Processing...', estimateProgress(data.progress));
      } else if (data.status === 'completed') {
        stopPolling();
        renderResults(data.data);
      } else if (data.status === 'failed') {
        stopPolling();
        showError(data.error || 'An error occurred during analysis.');
      }
    } catch (err) {
      stopPolling();
      showError('Connection lost. Please try again.');
    }
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
  resetButton();
}

function estimateProgress(progressText) {
  if (!progressText) return 15;
  if (progressText.includes('transcript')) return 20;
  if (progressText.includes('Analyzing')) return 35;
  if (progressText.includes('Fact-checking')) {
    const match = progressText.match(/(\d+)\/(\d+)/);
    if (match) {
      const pct = 40 + (parseInt(match[1]) / parseInt(match[2])) * 55;
      return Math.min(95, Math.round(pct));
    }
    return 50;
  }
  if (progressText.includes('Done')) return 100;
  return 25;
}

function updateProgress(text, pct) {
  document.getElementById('loading-status').textContent = text;
  document.getElementById('progress-fill').style.width = pct + '%';
}

// --- Render Results ---

function renderResults(data) {
  allClaims = data.claims || [];

  // Video info
  document.getElementById('video-title').textContent = data.video_title || 'Untitled Video';
  document.getElementById('video-title').dataset.videoId = data.video_id || '';

  const mins = Math.floor(data.video_duration_seconds / 60);
  const secs = Math.round(data.video_duration_seconds % 60);
  document.getElementById('video-duration').textContent = `${mins}:${secs.toString().padStart(2, '0')} duration`;
  document.getElementById('processing-time').textContent = `Analyzed in ${data.processing_time_seconds}s`;

  // Overall score
  const score = data.overall_truth_percentage;
  document.getElementById('score-value').textContent = score;
  document.getElementById('summary-text').textContent = data.summary || '';

  // Animate score ring
  const circle = document.getElementById('score-circle');
  const circumference = 339.3;
  const offset = circumference - (score / 100) * circumference;
  circle.style.strokeDashoffset = offset;
  circle.style.stroke = getScoreColor(score);

  // Render claims
  renderClaimsList(allClaims);

  showSection('results');
}

function renderClaimsList(claims) {
  const container = document.getElementById('claims-list');
  container.innerHTML = '';

  if (claims.length === 0) {
    container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No claims found.</p>';
    return;
  }

  claims.forEach((claim, i) => {
    const card = document.createElement('div');
    card.className = `claim-card`;
    card.dataset.category = claim.category;

    const badgeClass = getBadgeClass(claim.truth_percentage, claim.category);
    const badgeText = claim.category === 'opinion' ? 'Opinion' : `${claim.truth_percentage}%`;

    const timestamp = formatTimestamp(claim.timestamp_seconds);
    const ytLink = `https://youtube.com/watch?v=${document.getElementById('video-title').dataset.videoId || ''}&t=${Math.floor(claim.timestamp_seconds)}`;

    let sourcesHtml = '';
    if (claim.sources && claim.sources.length > 0) {
      sourcesHtml = '<div class="claim-sources">' +
        claim.sources.slice(0, 3).map(s =>
          `<a href="${s.url}" target="_blank" rel="noopener" class="source-link">${s.title}</a>`
        ).join('') +
        '</div>';
    }

    card.innerHTML = `
      <div class="claim-header">
        <span class="claim-text">${escapeHtml(claim.text)}</span>
        <span class="claim-badge ${badgeClass}">${badgeText}</span>
      </div>
      <div class="claim-meta">
        <span class="category-tag">${claim.category}</span>
        <span>${timestamp}</span>
        ${claim.confidence ? `<span>Confidence: ${Math.round(claim.confidence * 100)}%</span>` : ''}
      </div>
      <button class="claim-toggle" onclick="toggleClaim(this)">
        Show details &#9662;
      </button>
      <div class="claim-reasoning">${escapeHtml(claim.reasoning)}</div>
      ${sourcesHtml}
    `;

    container.appendChild(card);
  });
}

function toggleClaim(btn) {
  const card = btn.closest('.claim-card');
  card.classList.toggle('expanded');
  btn.innerHTML = card.classList.contains('expanded')
    ? 'Hide details &#9652;'
    : 'Show details &#9662;';
}

function filterClaims(filter) {
  // Update active button
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.filter-btn[data-filter="${filter}"]`).classList.add('active');

  const filtered = filter === 'all'
    ? allClaims
    : allClaims.filter(c => c.category === filter);

  renderClaimsList(filtered);
}

// --- Helpers ---

function getScoreColor(score) {
  if (score >= 75) return '#2ed573';
  if (score >= 50) return '#ffa502';
  return '#ff4757';
}

function getBadgeClass(score, category) {
  if (category === 'opinion') return 'badge-gray';
  if (score >= 75) return 'badge-green';
  if (score >= 50) return 'badge-yellow';
  return 'badge-red';
}

function formatTimestamp(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// --- UI State ---

function showSection(name) {
  ['loading', 'error', 'results'].forEach(s => {
    document.getElementById(`${s}-section`).style.display = s === name ? 'block' : 'none';
  });
}

function showError(message) {
  document.getElementById('error-message').textContent = message;
  showSection('error');
  resetButton();
}

function resetButton() {
  const btn = document.getElementById('check-btn');
  btn.disabled = false;
  btn.querySelector('.btn-text').style.display = 'inline';
  btn.querySelector('.btn-loading').style.display = 'none';
}

function resetUI() {
  stopPolling();
  showSection(null);
  ['loading', 'error', 'results'].forEach(s => {
    document.getElementById(`${s}-section`).style.display = 'none';
  });
  document.getElementById('url-input').value = '';
  document.getElementById('input-error').textContent = '';
  resetButton();
  allClaims = [];
}

// Enter key support
document.getElementById('url-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') submitVideo();
});
