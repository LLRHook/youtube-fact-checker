/* YouTube Fact Checker — Public Video Detail */

let allVideoClaims = [];

document.addEventListener('DOMContentLoaded', () => {
  const parts = window.location.pathname.split('/');
  const videoId = parts[parts.length - 1];
  if (videoId) loadVideo(videoId);
});

async function loadVideo(videoId) {
  const container = document.getElementById('content');
  try {
    const resp = await fetch(`/api/videos/${videoId}`);
    if (!resp.ok) {
      container.innerHTML = '<div class="empty-state">Video not found.</div>';
      return;
    }
    const video = await resp.json();
    renderVideo(video);
    document.title = `${video.title} — YouTube Fact Checker`;
  } catch (err) {
    container.innerHTML = '<div class="empty-state">Error loading video.</div>';
  }
}

function renderVideo(video) {
  const container = document.getElementById('content');
  const scoreColor = video.public_score >= 75 ? '#2ed573' : video.public_score >= 50 ? '#ffa502' : '#ff4757';
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (video.public_score / 100) * circumference;

  allVideoClaims = video.claims || [];

  let claimsHtml = '';
  if (video.claims && video.claims.length > 0) {
    claimsHtml = video.claims.map(c => {
      const badgeClass = getBadgeClass(c.truth_percentage, c.category);
      const badgeText = c.category === 'opinion' ? 'Opinion' : `${getVerdictLabel(c.truth_percentage)} · ${c.truth_percentage}%`;
      const ts = formatTimestamp(c.timestamp_seconds);
      const seekSeconds = Math.floor(c.timestamp_seconds);

      let sourcesHtml = '';
      if (c.sources && c.sources.length > 0) {
        sourcesHtml = '<div class="claim-sources">' +
          c.sources.map(s =>
            `<a href="${s.url}" target="_blank" rel="noopener" class="source-link">${escapeHtml(s.title)}</a>` +
            (s.snippet ? `<p class="source-snippet">${escapeHtml(s.snippet)}</p>` : '')
          ).join('') + '</div>';
      }

      const borderClass = getBorderClass(c.truth_percentage, c.category);
      return `
        <div class="claim-card ${borderClass}">
          <div class="claim-header">
            <span class="claim-text">${escapeHtml(c.text)}</span>
            <span class="claim-badge ${badgeClass}">${badgeText}</span>
          </div>
          <div class="claim-meta">
            <span class="category-tag">${c.category}</span>
            <a href="#" onclick="seekTo(${seekSeconds});return false;" style="color:var(--blue);text-decoration:none;cursor:pointer;">${ts}</a>
          </div>
          <button class="claim-toggle" onclick="toggleClaim(this)">Show details &#9662;</button>
          <div class="claim-reasoning">${escapeHtml(c.reasoning)}</div>
          ${sourcesHtml}
        </div>
      `;
    }).join('');
  } else {
    claimsHtml = '<div class="empty-state">No claims for this video.</div>';
  }

  const channelLink = video.channel
    ? `<a href="/channel/${encodeURIComponent(video.channel)}">${escapeHtml(video.channel)}</a>`
    : '';

  container.innerHTML = `
    <div class="video-embed">
      <iframe id="yt-player"
        src="https://www.youtube-nocookie.com/embed/${video.id}?enablejsapi=1&rel=0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen></iframe>
    </div>

    <div class="video-info">
      <h1>${escapeHtml(video.title)}</h1>
      <div class="video-meta">
        ${channelLink}
        <span>${formatDate(video.created_at)}</span>
      </div>
    </div>

    <div class="score-section">
      <div class="score-ring">
        <svg viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" stroke="#2a2a4a" stroke-width="8" fill="none"/>
          <circle cx="60" cy="60" r="54" stroke="${scoreColor}" stroke-width="8" fill="none"
                  stroke-dasharray="${circumference}"
                  stroke-dashoffset="${offset}"
                  stroke-linecap="round"
                  transform="rotate(-90 60 60)"/>
        </svg>
        <div class="score-text">
          <span class="score-value">${video.public_score}</span>
          <span class="score-pct">%</span>
        </div>
      </div>
      <div class="score-label">
        <h3>Accuracy Score</h3>
        <p>${escapeHtml(video.summary)}</p>
      </div>
    </div>

    <button class="share-btn" onclick="copyShareLink()">Share this page</button>

    <div id="breakdown-bar" class="breakdown-bar-container"></div>

    <h3 class="claims-heading">Claims (${video.claims.length})</h3>
    <div class="filter-bar">
      <button class="filter-btn active" data-filter="all" onclick="filterVideoClaims('all')">All</button>
      <button class="filter-btn" data-filter="fact" onclick="filterVideoClaims('fact')">Facts</button>
      <button class="filter-btn" data-filter="opinion" onclick="filterVideoClaims('opinion')">Opinions</button>
      <button id="toggle-all-btn" class="filter-btn" onclick="toggleAllClaims()" style="margin-left:auto;">Expand all</button>
    </div>
    <div id="claims-container">${claimsHtml}</div>
  `;

  renderBreakdownBar(allVideoClaims);
  updateVideoFilterCounts(allVideoClaims);
}

function renderBreakdownBar(claims) {
  const container = document.getElementById('breakdown-bar');
  if (!container) return;
  const facts = claims.filter(c => c.category === 'fact');
  const opinions = claims.filter(c => c.category === 'opinion');
  const trueCount = facts.filter(c => c.truth_percentage >= 75).length;
  const mixedCount = facts.filter(c => c.truth_percentage >= 50 && c.truth_percentage < 75).length;
  const falseCount = facts.filter(c => c.truth_percentage < 50).length;
  const total = claims.length || 1;

  container.innerHTML = `
    <div class="breakdown-segments">
      ${trueCount ? `<div class="breakdown-seg seg-green" style="width:${(trueCount/total)*100}%"></div>` : ''}
      ${mixedCount ? `<div class="breakdown-seg seg-yellow" style="width:${(mixedCount/total)*100}%"></div>` : ''}
      ${falseCount ? `<div class="breakdown-seg seg-red" style="width:${(falseCount/total)*100}%"></div>` : ''}
      ${opinions.length ? `<div class="breakdown-seg seg-gray" style="width:${(opinions.length/total)*100}%"></div>` : ''}
    </div>
    <div class="breakdown-legend">
      ${trueCount ? `<span class="legend-item"><span class="legend-dot dot-green"></span>${trueCount} true</span>` : ''}
      ${mixedCount ? `<span class="legend-item"><span class="legend-dot dot-yellow"></span>${mixedCount} mixed</span>` : ''}
      ${falseCount ? `<span class="legend-item"><span class="legend-dot dot-red"></span>${falseCount} false</span>` : ''}
      ${opinions.length ? `<span class="legend-item"><span class="legend-dot dot-gray"></span>${opinions.length} opinion</span>` : ''}
    </div>
  `;
}

function updateVideoFilterCounts(claims) {
  const factCount = claims.filter(c => c.category === 'fact').length;
  const opinionCount = claims.filter(c => c.category === 'opinion').length;
  const allBtn = document.querySelector('.filter-btn[data-filter="all"]');
  const factBtn = document.querySelector('.filter-btn[data-filter="fact"]');
  const opinionBtn = document.querySelector('.filter-btn[data-filter="opinion"]');
  if (allBtn) allBtn.textContent = `All (${claims.length})`;
  if (factBtn) factBtn.textContent = `Facts (${factCount})`;
  if (opinionBtn) opinionBtn.textContent = `Opinions (${opinionCount})`;
}

function toggleClaim(btn) {
  const card = btn.closest('.claim-card');
  card.classList.toggle('expanded');
  btn.innerHTML = card.classList.contains('expanded')
    ? 'Hide details &#9652;'
    : 'Show details &#9662;';
}

function toggleAllClaims() {
  const cards = document.querySelectorAll('#claims-container .claim-card');
  const btn = document.getElementById('toggle-all-btn');
  const anyCollapsed = Array.from(cards).some(c => !c.classList.contains('expanded'));
  cards.forEach(c => {
    c.classList.toggle('expanded', anyCollapsed);
    const toggle = c.querySelector('.claim-toggle');
    if (toggle) toggle.innerHTML = anyCollapsed ? 'Hide details &#9652;' : 'Show details &#9662;';
  });
  btn.textContent = anyCollapsed ? 'Collapse all' : 'Expand all';
}

function filterVideoClaims(filter) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.filter-btn[data-filter="${filter}"]`).classList.add('active');

  const container = document.getElementById('claims-container');
  if (!container) return;

  const filtered = filter === 'all'
    ? allVideoClaims
    : allVideoClaims.filter(c => c.category === filter);

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty-state">No matching claims.</div>';
    return;
  }

  container.innerHTML = filtered.map(c => {
    const badgeClass = getBadgeClass(c.truth_percentage, c.category);
    const badgeText = c.category === 'opinion' ? 'Opinion' : `${getVerdictLabel(c.truth_percentage)} · ${c.truth_percentage}%`;
    const ts = formatTimestamp(c.timestamp_seconds);
    const seekSeconds = Math.floor(c.timestamp_seconds);

    let sourcesHtml = '';
    if (c.sources && c.sources.length > 0) {
      sourcesHtml = '<div class="claim-sources">' +
        c.sources.map(s =>
          `<a href="${s.url}" target="_blank" rel="noopener" class="source-link">${escapeHtml(s.title)}</a>` +
          (s.snippet ? `<p class="source-snippet">${escapeHtml(s.snippet)}</p>` : '')
        ).join('') + '</div>';
    }

    const borderClass = getBorderClass(c.truth_percentage, c.category);
    return `
      <div class="claim-card ${borderClass}">
        <div class="claim-header">
          <span class="claim-text">${escapeHtml(c.text)}</span>
          <span class="claim-badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="claim-meta">
          <span class="category-tag">${c.category}</span>
          <a href="#" onclick="seekTo(${seekSeconds});return false;" style="color:var(--blue);text-decoration:none;cursor:pointer;">${ts}</a>
        </div>
        <button class="claim-toggle" onclick="toggleClaim(this)">Show details &#9662;</button>
        <div class="claim-reasoning">${escapeHtml(c.reasoning)}</div>
        ${sourcesHtml}
      </div>
    `;
  }).join('');
}

function copyShareLink() {
  navigator.clipboard.writeText(window.location.href).then(() => {
    const btn = document.querySelector('.share-btn');
    btn.textContent = 'Link copied!';
    setTimeout(() => { btn.textContent = 'Share this page'; }, 2000);
  });
}

function getBadgeClass(score, category) {
  if (category === 'opinion') return 'badge-gray';
  if (score >= 75) return 'badge-green';
  if (score >= 50) return 'badge-yellow';
  return 'badge-red';
}

function getVerdictLabel(score) {
  if (score >= 75) return 'True';
  if (score >= 50) return 'Mixed';
  return 'False';
}

function getBorderClass(score, category) {
  if (category === 'opinion') return 'border-gray';
  if (score >= 75) return 'border-green';
  if (score >= 50) return 'border-yellow';
  return 'border-red';
}

function formatTimestamp(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'Z');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function seekTo(seconds) {
  const iframe = document.getElementById('yt-player');
  if (iframe) {
    iframe.contentWindow.postMessage(JSON.stringify({
      event: 'command',
      func: 'seekTo',
      args: [seconds, true]
    }), '*');
    iframe.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
