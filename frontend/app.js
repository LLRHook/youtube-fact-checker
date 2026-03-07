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

    if (data.status === 'queued') {
      showSection('queued');
      resetButton();
      return;
    }

    // Show loading
    showSection('loading');
    document.getElementById('loading-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
    startPolling();

  } catch (err) {
    errorEl.textContent = err.message;
    resetButton();
    return;
  }
}

// --- Polling ---

function startPolling() {
  updateProgress('Starting analysis...', 10);
  startElapsedTimer();
  pollFailures = 0;

  pollTimeout = setTimeout(() => {
    stopPolling();
    showError('Analysis is taking too long. The video may still be processing — check the Videos page later.');
  }, POLL_TIMEOUT_MS);

  pollInterval = setInterval(async () => {
    try {
      const resp = await fetch(`/api/check/${currentTaskId}`);
      if (!resp.ok) throw new Error('Polling failed');

      const data = await resp.json();
      pollFailures = 0;

      if (data.status === 'processing') {
        updateProgress(data.progress || 'Processing...', estimateProgress(data.progress));
      } else if (data.status === 'completed') {
        stopPolling();
        renderResults(data.data);
      } else if (data.status === 'failed') {
        stopPolling();
        showError(data.error || 'An error occurred during analysis.');
      } else if (data.status === 'queued') {
        stopPolling();
        showSection('queued');
      }
    } catch (err) {
      pollFailures++;
      if (pollFailures >= MAX_POLL_FAILURES) {
        stopPolling();
        showError('Connection lost. Please try again.');
      }
    }
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
  if (pollTimeout) {
    clearTimeout(pollTimeout);
    pollTimeout = null;
  }
  stopElapsedTimer();
  resetButton();
}

function startElapsedTimer() {
  elapsedStart = Date.now();
  const el = document.getElementById('loading-elapsed');
  if (el) el.textContent = 'Elapsed: 0s';
  elapsedInterval = setInterval(() => {
    if (el) el.textContent = `Elapsed: ${Math.round((Date.now() - elapsedStart) / 1000)}s`;
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
  document.title = `${pct}% — ${text} | YouTube Fact Checker`;
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
  document.getElementById('summary-text').textContent = data.summary || '';

  // Animate score ring
  const circle = document.getElementById('score-circle');
  const circumference = 339.3;
  const offset = circumference - (score / 100) * circumference;
  circle.style.strokeDashoffset = offset;
  circle.style.stroke = scoreColor(score);

  // Color & animate score counter
  document.getElementById('score-value').style.color = scoreColor(score);
  animateCounter('score-value', 0, score, 800);

  // Render breakdown stats
  renderBreakdownBar(allClaims);

  // Render claims
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
  document.getElementById('results-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
    const borderClass = getBorderClass(claim.truth_percentage, claim.category);
    card.className = `claim-card claim-enter ${borderClass}`;
    card.style.animationDelay = `${i * 60}ms`;
    card.dataset.category = claim.category;

    const badgeClass = getBadgeClass(claim.truth_percentage, claim.category);
    const badgeText = claim.category === 'opinion' ? 'Opinion' : `${verdictLabel(claim.truth_percentage)} · ${claim.truth_percentage}%`;
    const badgeTitle = claim.category === 'opinion' ? 'This is an opinion, not a factual claim' : `Accuracy score: ${claim.truth_percentage}% — ${verdictLabel(claim.truth_percentage)}`;

    const timestamp = formatTimestamp(claim.timestamp_seconds);
    const ytLink = `https://youtube.com/watch?v=${document.getElementById('video-title').dataset.videoId || ''}&t=${Math.floor(claim.timestamp_seconds)}`;

    let sourcesHtml = '';
    if (claim.sources && claim.sources.length > 0) {
      sourcesHtml = '<div class="claim-sources">' +
        claim.sources.slice(0, 3).map(s =>
          `<a href="${s.url}" target="_blank" rel="noopener" class="source-link">${escapeHtml(s.title)}</a>` +
          (s.snippet ? `<p class="source-snippet">${escapeHtml(s.snippet)}</p>` : '')
        ).join('') +
        '</div>';
    }

    card.innerHTML = `
      <div class="claim-header">
        <span class="claim-text"><span class="claim-num">#${i + 1}</span> ${escapeHtml(claim.text)}</span>
        <span class="claim-badge ${badgeClass}" title="${badgeTitle}">${badgeText}</span>
      </div>
      <div class="claim-meta">
        <span class="category-tag">${claim.category}</span>
        <a href="${ytLink}" target="_blank" rel="noopener" style="color:var(--blue);text-decoration:none;">${timestamp}</a>
        ${claim.confidence ? `<span>Confidence: ${Math.round(claim.confidence * 100)}%</span>` : ''}
        ${claim.sources && claim.sources.length > 0 ? `<span>${claim.sources.length} source${claim.sources.length > 1 ? 's' : ''}</span>` : ''}
      </div>
      <button class="claim-toggle" onclick="event.stopPropagation();toggleClaim(this)">
        Show details &#9662;
      </button>
      <div class="claim-reasoning">${escapeHtml(claim.reasoning)}</div>
      ${sourcesHtml}
    `;

    card.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
      toggleClaim(card.querySelector('.claim-toggle'));
    });

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

function toggleAllClaims() {
  const cards = document.querySelectorAll('#claims-list .claim-card');
  const btn = document.getElementById('toggle-all-btn');
  const anyCollapsed = Array.from(cards).some(c => !c.classList.contains('expanded'));
  cards.forEach(c => {
    c.classList.toggle('expanded', anyCollapsed);
    const toggle = c.querySelector('.claim-toggle');
    if (toggle) toggle.innerHTML = anyCollapsed ? 'Hide details &#9652;' : 'Show details &#9662;';
  });
  btn.textContent = anyCollapsed ? 'Collapse all' : 'Expand all';
}

function updateFilterCounts(claims) {
  const factCount = claims.filter(c => c.category === 'fact').length;
  const opinionCount = claims.filter(c => c.category === 'opinion').length;
  const allBtn = document.querySelector('.filter-btn[data-filter="all"]');
  const factBtn = document.querySelector('.filter-btn[data-filter="fact"]');
  const opinionBtn = document.querySelector('.filter-btn[data-filter="opinion"]');
  if (allBtn) allBtn.textContent = `All (${claims.length})`;
  if (factBtn) factBtn.textContent = `Facts (${factCount})`;
  if (opinionBtn) opinionBtn.textContent = `Opinions (${opinionCount})`;
}

function cancelAnalysis() {
  stopPolling();
  currentTaskId = null;
  document.title = 'YouTube Fact Checker';
  showSection(null);
  ['loading', 'error', 'results', 'queued'].forEach(s => {
    document.getElementById(`${s}-section`).style.display = 'none';
  });
  resetButton();
}

// --- Helpers ---

// --- UI State ---

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
  document.getElementById('error-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  ['loading', 'error', 'results', 'queued'].forEach(s => {
    document.getElementById(`${s}-section`).style.display = 'none';
  });
  document.getElementById('url-input').value = '';
  document.getElementById('input-error').textContent = '';
  document.getElementById('url-preview').style.display = 'none';
  document.getElementById('view-report-link').style.display = 'none';
  resetButton();
  allClaims = [];
}

// Enter key support
document.getElementById('url-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') submitVideo();
});

// URL preview on input
document.getElementById('url-input').addEventListener('input', showUrlPreview);
document.getElementById('url-input').addEventListener('paste', () => {
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
      const expanded = document.querySelectorAll('#claims-list .claim-card.expanded');
      if (expanded.length > 0) {
        expanded.forEach(c => {
          c.classList.remove('expanded');
          const toggle = c.querySelector('.claim-toggle');
          if (toggle) toggle.innerHTML = 'Show details &#9662;';
        });
        const btn = document.getElementById('toggle-all-btn');
        if (btn) btn.textContent = 'Expand all';
      } else {
        const input = document.getElementById('url-input');
        if (input.value) {
          input.value = '';
          document.getElementById('url-preview').style.display = 'none';
          document.getElementById('input-error').textContent = '';
          input.focus();
        } else {
          input.blur();
        }
      }
    }
  }
});

function showUrlPreview() {
  const url = document.getElementById('url-input').value.trim();
  const preview = document.getElementById('url-preview');
  const ytRegex = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/;
  const match = url.match(ytRegex);

  if (match) {
    const videoId = match[1];
    document.getElementById('preview-thumb').src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    document.getElementById('preview-id').textContent = `Video ID: ${videoId}`;
    preview.style.display = 'flex';
  } else {
    preview.style.display = 'none';
  }
}
