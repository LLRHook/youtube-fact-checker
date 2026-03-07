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
      const badgeText = c.category === 'opinion' ? 'Opinion' : `${c.truth_percentage}%`;
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

      return `
        <div class="claim-card">
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

    <h3 class="claims-heading">Claims (${video.claims.length})</h3>
    <div class="filter-bar">
      <button class="filter-btn active" data-filter="all" onclick="filterVideoClaims('all')">All</button>
      <button class="filter-btn" data-filter="fact" onclick="filterVideoClaims('fact')">Facts</button>
      <button class="filter-btn" data-filter="opinion" onclick="filterVideoClaims('opinion')">Opinions</button>
      <button id="toggle-all-btn" class="filter-btn" onclick="toggleAllClaims()" style="margin-left:auto;">Expand all</button>
    </div>
    <div id="claims-container">${claimsHtml}</div>
  `;
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
    const badgeText = c.category === 'opinion' ? 'Opinion' : `${c.truth_percentage}%`;
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

    return `
      <div class="claim-card">
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
