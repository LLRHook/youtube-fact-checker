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
      container.innerHTML = `<div class="empty-state">
        <p class="empty-heading">Video not found</p>
        <p class="empty-text">This video hasn't been fact-checked yet, or the URL is invalid.</p>
        <div class="empty-links">
          <a href="/" class="empty-link">Check a video</a>
          <a href="/videos" class="empty-link">Browse videos</a>
        </div>
      </div>`;
      document.title = 'Not Found — YouTube Fact Checker';
      return;
    }
    const video = await resp.json();
    renderVideo(video);
    const claimCount = (video.claims || []).length;
    document.title = `${video.title} (${claimCount} claim${claimCount !== 1 ? 's' : ''}) — YouTube Fact Checker`;
    setMeta('meta[property="og:title"]', `${video.title} — YouTube Fact Checker`);
    setMeta('meta[property="og:image"]', `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`);
    if (video.summary) {
      setMeta('meta[property="og:description"]', video.summary);
      setMeta('meta[name="description"]', video.summary);
    }
  } catch (err) {
    container.innerHTML = `<div class="empty-state">
      <p class="empty-heading">Error loading video</p>
      <p class="empty-text">Something went wrong. Please try again later.</p>
      <a href="/videos" class="empty-link">Browse videos</a>
    </div>`;
  }
}

function buildClaimCardHtml(c, i) {
  const badgeClass = getBadgeClass(c.truth_percentage, c.category);
  const bt = badgeText(c.truth_percentage, c.category);
  const btTitle = badgeTitle(c.truth_percentage, c.category);
  const ts = formatTimestamp(c.timestamp_seconds);
  const seekSeconds = Math.floor(c.timestamp_seconds);

  const sourcesHtml = buildSourcesHtml(c.sources);

  const borderClass = getBorderClass(c.truth_percentage, c.category);
  return `
    <div class="claim-card claim-enter ${borderClass}" style="animation-delay:${i * 60}ms">
      <div class="claim-header">
        <span class="claim-text"><span class="claim-num">#${c._num || i + 1}</span> ${escapeHtml(c.text)}</span>
        <span class="claim-badge ${badgeClass}" title="${btTitle}">${bt}</span>
      </div>
      <div class="claim-meta">
        <span class="category-tag">${c.category}</span>
        <a href="#" onclick="seekTo(${seekSeconds});return false;">${ts}</a>
        ${c.confidence ? `<span>Confidence: ${Math.round(c.confidence * 100)}%</span>` : ''}
        ${sourceCountHtml(c.sources)}
      </div>
      <button class="claim-toggle" onclick="event.stopPropagation();toggleClaim(this)">Show details &#9662;</button>
      <div class="claim-reasoning">${escapeHtml(c.reasoning)}</div>
      ${sourcesHtml}
    </div>
  `;
}

function renderVideo(video) {
  const container = document.getElementById('content');
  const sc = scoreColor(video.public_score);
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (video.public_score / 100) * circumference;

  allVideoClaims = (video.claims || []).map((c, i) => ({...c, _num: i + 1}));

  const claimsHtml = allVideoClaims.length > 0
    ? allVideoClaims.map((c, i) => buildClaimCardHtml(c, i)).join('')
    : '<div class="empty-state">No claims for this video.</div>';

  const channelLink = video.channel
    ? `<a href="/channel/${encodeURIComponent(video.channel)}">${escapeHtml(video.channel)}</a>`
    : '';

  container.innerHTML = `
    <div class="video-embed">
      <iframe id="yt-player"
        src="https://www.youtube-nocookie.com/embed/${video.id}?enablejsapi=1&rel=0"
        title="${escapeHtml(video.title)}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen></iframe>
    </div>

    <div class="video-info">
      <h1>${escapeHtml(video.title)}</h1>
      <div class="video-meta">
        ${channelLink}
        <span title="${absoluteDate(video.created_at)}">${formatDate(video.created_at)}</span>
      </div>
    </div>

    <div class="overall-score">
      <div class="score-ring">
        <svg viewBox="0 0 120 120" role="img" aria-label="Accuracy score: ${video.public_score}%">
          <circle cx="60" cy="60" r="54" stroke="var(--border)" stroke-width="8" fill="none"/>
          <circle cx="60" cy="60" r="54" stroke="${sc}" stroke-width="8" fill="none"
                  id="score-ring-circle"
                  stroke-dasharray="${circumference}"
                  stroke-dashoffset="${circumference}"
                  stroke-linecap="round"
                  transform="rotate(-90 60 60)"/>
        </svg>
        <div class="score-text">
          <span class="score-value" id="score-value" style="color:${sc}">0</span>
          <span class="score-percent">%</span>
        </div>
      </div>
      <div class="score-label">
        <h3>Accuracy Score</h3>
        <p>${escapeHtml(video.summary)}</p>
      </div>
    </div>

    <div class="action-row">
      <button class="share-btn" onclick="copyShareLink()">Share this page</button>
      <a href="https://www.youtube.com/watch?v=${video.id}" target="_blank" rel="noopener" class="share-btn share-btn--link">Open on YouTube</a>
    </div>

    <div id="breakdown-bar" class="breakdown-bar-container"></div>

    <h3 class="claims-heading">Claims (${allVideoClaims.length})</h3>
    <div class="filter-bar" role="toolbar" aria-label="Filter claims by category">
      <button class="filter-btn active" data-filter="all" onclick="filterVideoClaims('all')">All</button>
      <button class="filter-btn" data-filter="fact" onclick="filterVideoClaims('fact')">Facts</button>
      <button class="filter-btn" data-filter="opinion" onclick="filterVideoClaims('opinion')">Opinions</button>
      <button id="toggle-all-btn" class="filter-btn filter-btn--end" onclick="toggleAllClaims('claims-container')">Expand all</button>
    </div>
    <div id="claims-container">${claimsHtml}</div>
  `;

  addCardClickListeners('claims-container');
  renderBreakdownBar(allVideoClaims);
  updateFilterCounts(allVideoClaims);
  animateCounter('score-value', 0, video.public_score, 800);

  requestAnimationFrame(() => {
    const ring = document.getElementById('score-ring-circle');
    if (ring) ring.setAttribute('stroke-dashoffset', offset);
  });
}

function filterVideoClaims(filter) {
  setActiveFilter(filter);

  const container = document.getElementById('claims-container');
  if (!container) return;

  const filtered = filter === 'all'
    ? allVideoClaims
    : allVideoClaims.filter(c => c.category === filter);

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty-state">No matching claims.</div>';
    return;
  }

  container.innerHTML = filtered.map((c, i) => buildClaimCardHtml(c, i)).join('');
  addCardClickListeners('claims-container');
}

async function copyShareLink() {
  const btn = document.querySelector('.share-btn');
  try {
    await navigator.clipboard.writeText(window.location.href);
    btn.textContent = 'Link copied!';
  } catch {
    btn.textContent = 'Copy failed';
  }
  setTimeout(() => { btn.textContent = 'Share this page'; }, 2000);
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (!collapseAllCards('claims-container')) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }
});

function seekTo(seconds) {
  const iframe = document.getElementById('yt-player');
  if (iframe) {
    iframe.contentWindow.postMessage(JSON.stringify({
      event: 'command',
      func: 'seekTo',
      args: [seconds, true]
    }), 'https://www.youtube-nocookie.com');
    iframe.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
