/* YouTube Fact Checker — Shared Utilities */

function escapeHtml(str) {
  if (str == null) return '';
  str = String(str);
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const hasTimezone = dateStr.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(dateStr);
  const d = new Date(hasTimezone ? dateStr : dateStr + 'Z');
  const now = new Date();
  const diffMs = now - d;
  if (diffMs < 0) return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function absoluteDate(dateStr) {
  if (!dateStr) return '';
  const hasTimezone = dateStr.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(dateStr);
  return new Date(hasTimezone ? dateStr : dateStr + 'Z').toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

function formatTimestamp(seconds) {
  if (!seconds && seconds !== 0) return '0:00';
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function getBadgeClass(score, category) {
  if (category === 'opinion') return 'badge-gray';
  if (score >= 75) return 'badge-green';
  if (score >= 50) return 'badge-yellow';
  return 'badge-red';
}

function getBorderClass(score, category) {
  if (category === 'opinion') return 'border-gray';
  if (score >= 75) return 'border-green';
  if (score >= 50) return 'border-yellow';
  return 'border-red';
}

function animateCounter(elementId, from, to, duration) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const start = performance.now();
  function tick(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(from + (to - from) * eased);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function verdictLabel(score) {
  if (score >= 75) return 'True';
  if (score >= 50) return 'Mixed';
  return 'False';
}

function scoreClass(score) {
  if (score >= 75) return 'score-green';
  if (score >= 50) return 'score-yellow';
  return 'score-red';
}

function scoreColor(score) {
  const style = getComputedStyle(document.documentElement);
  if (score >= 75) return style.getPropertyValue('--green').trim() || '#2ed573';
  if (score >= 50) return style.getPropertyValue('--yellow').trim() || '#ffa502';
  return style.getPropertyValue('--red').trim() || '#ff4757';
}

function buildBreakdownHtml(segments) {
  const total = segments.reduce((sum, s) => sum + s.count, 0) || 1;
  const active = segments.filter(s => s.count > 0);
  return `
    <div class="breakdown-segments">
      ${active.map(s => `<div class="breakdown-seg seg-${s.color}" title="${s.count} ${s.label}" style="width:${(s.count/total)*100}%"></div>`).join('')}
    </div>
    <div class="breakdown-legend">
      ${active.map(s => `<span class="legend-item"><span class="legend-dot dot-${s.color}"></span>${s.count} ${s.label}</span>`).join('')}
    </div>
  `;
}

function renderBreakdownBar(claims) {
  const container = document.getElementById('breakdown-bar');
  if (!container) return;
  const facts = claims.filter(c => c.category === 'fact' || c.category === 'unclear');
  const opinions = claims.filter(c => c.category === 'opinion');
  container.innerHTML = buildBreakdownHtml([
    { count: facts.filter(c => c.truth_percentage >= 75).length, label: 'true', color: 'green' },
    { count: facts.filter(c => c.truth_percentage >= 50 && c.truth_percentage < 75).length, label: 'mixed', color: 'yellow' },
    { count: facts.filter(c => c.truth_percentage < 50).length, label: 'false', color: 'red' },
    { count: opinions.length, label: 'opinion', color: 'gray' },
  ]);
}

/* --- Theme --- */

function initTheme() {
  try {
    const saved = localStorage.getItem('theme');
    if (saved) {
      document.documentElement.setAttribute('data-theme', saved);
    } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
      document.documentElement.setAttribute('data-theme', 'light');
    }
  } catch (_) {}
  updateToggleIcon();
  updateThemeMeta();
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('theme', next); } catch (_) {}
  updateToggleIcon();
  updateThemeMeta();
}

function updateToggleIcon() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  const theme = document.documentElement.getAttribute('data-theme');
  const label = theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode';
  btn.innerHTML = theme === 'light' ? '&#9790;' : '&#9728;';
  btn.title = label;
  btn.setAttribute('aria-label', label);
}

function updateThemeMeta() {
  const theme = document.documentElement.getAttribute('data-theme');
  setMeta('meta[name="theme-color"]', theme === 'light' ? '#f5f5f7' : '#0f0f0f');
}

initTheme();

/* --- Claim Card Interactions --- */

function toggleClaim(btn) {
  const card = btn.closest('.claim-card');
  card.classList.toggle('expanded');
  const isExpanded = card.classList.contains('expanded');
  btn.innerHTML = isExpanded ? 'Hide details &#9652;' : 'Show details &#9662;';
  btn.setAttribute('aria-expanded', isExpanded);
}

function addCardClickListeners(containerId) {
  document.querySelectorAll(`#${containerId} .claim-card`).forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
      const toggle = card.querySelector('.claim-toggle');
      if (toggle) toggleClaim(toggle);
    });
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const toggle = card.querySelector('.claim-toggle');
        if (toggle) toggleClaim(toggle);
      }
    });
  });
}

/* --- Filter Counts --- */

function updateFilterCounts(claims) {
  const factCount = claims.filter(c => c.category === 'fact' || c.category === 'unclear').length;
  const opinionCount = claims.filter(c => c.category === 'opinion').length;
  const allBtn = document.querySelector('.filter-btn[data-filter="all"]');
  const factBtn = document.querySelector('.filter-btn[data-filter="fact"]');
  const opinionBtn = document.querySelector('.filter-btn[data-filter="opinion"]');
  if (allBtn) allBtn.textContent = `All (${claims.length})`;
  if (factBtn) factBtn.textContent = `Facts (${factCount})`;
  if (opinionBtn) opinionBtn.textContent = `Opinions (${opinionCount})`;
}

/* --- Scroll Helper (respects prefers-reduced-motion) --- */

const _prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

function smoothScroll(el, block) {
  if (!el) return;
  el.scrollIntoView({ behavior: _prefersReducedMotion.matches ? 'auto' : 'smooth', block: block || 'start' });
}

/* --- Back to Top --- */

function initBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  window.addEventListener('scroll', () => {
    btn.classList.toggle('visible', window.scrollY > 400);
  }, { passive: true });
}

initBackToTop();

/* --- Badge Helpers --- */

function badgeText(score, category) {
  return category === 'opinion' ? 'Opinion' : `${verdictLabel(score)} · ${score}%`;
}

function badgeTitle(score, category) {
  return category === 'opinion' ? 'This is an opinion, not a factual claim' : `Accuracy score: ${score}% — ${verdictLabel(score)}`;
}

function scoreBadgeHtml(score) {
  return `<span class="score-badge ${scoreClass(score)}" title="Accuracy score: ${score}% — ${verdictLabel(score)}">${verdictLabel(score)} · ${score}%</span>`;
}

/* --- Meta Tag Helper --- */

function setMeta(selector, content) {
  const el = document.querySelector(selector);
  if (el) el.setAttribute('content', content);
}

/* --- Source Count --- */

function sourceCountHtml(sources) {
  if (!sources || sources.length === 0) return '';
  return `<span>${sources.length} source${sources.length > 1 ? 's' : ''}</span>`;
}

/* --- Sources HTML --- */

function buildSourcesHtml(sources, limit) {
  if (!sources || sources.length === 0) return '';
  const items = limit ? sources.slice(0, limit) : sources;
  const safe = items.filter(s => {
    if (!s.url) return false;
    try { new URL(s.url); } catch { return false; }
    return s.url.startsWith('https://') || s.url.startsWith('http://');
  });
  if (safe.length === 0) return '';
  return '<div class="claim-sources">' +
    safe.map(s =>
      `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" class="source-link">${escapeHtml(s.title || s.url)}</a>` +
      (s.snippet ? `<p class="source-snippet">${escapeHtml(s.snippet)}</p>` : '')
    ).join('') + '</div>';
}

/* --- Claim Card HTML --- */

function buildClaimCardHtml(c, i, { videoId, seekable, sourcesLimit } = {}) {
  const borderClass = getBorderClass(c.truth_percentage, c.category);
  const badgeClass = getBadgeClass(c.truth_percentage, c.category);
  const bt = badgeText(c.truth_percentage, c.category);
  const btTitle = badgeTitle(c.truth_percentage, c.category);
  const ts = formatTimestamp(c.timestamp_seconds);
  const seekSeconds = Math.max(0, Math.floor(c.timestamp_seconds)) || 0;
  const sourcesHtml = buildSourcesHtml(c.sources, sourcesLimit);

  const videoIdSafe = escapeHtml(videoId);
  const timestampLink = seekable
    ? `<a href="#" onclick="seekTo(${seekSeconds});return false;">${ts}</a>`
    : videoId
      ? `<a href="https://youtube.com/watch?v=${videoIdSafe}&t=${seekSeconds}" target="_blank" rel="noopener noreferrer">${ts}</a>`
      : `<span>${ts}</span>`;

  return `
    <div class="claim-card claim-enter ${borderClass}" tabindex="0" role="button" style="animation-delay:${i * 60}ms">
      <div class="claim-header">
        <span class="claim-text"><span class="claim-num">#${c._num || i + 1}</span> ${escapeHtml(c.text)}</span>
        <span class="claim-badge ${badgeClass}" title="${btTitle}">${bt}</span>
      </div>
      <div class="claim-meta">
        <span class="category-tag">${escapeHtml(c.category)}</span>
        ${timestampLink}
        ${c.confidence ? `<span>Confidence: ${Math.round(c.confidence * 100)}%</span>` : ''}
        ${sourceCountHtml(c.sources)}
      </div>
      <button class="claim-toggle" aria-expanded="false" onclick="event.stopPropagation();toggleClaim(this)">Show details &#9662;</button>
      <div class="claim-reasoning">${escapeHtml(c.reasoning)}</div>
      ${sourcesHtml}
    </div>
  `;
}

/* --- Active Filter --- */

function setActiveFilter(filter) {
  document.querySelectorAll('.filter-btn[data-filter]').forEach(b => {
    const isActive = b.dataset.filter === filter;
    b.classList.toggle('active', isActive);
    b.setAttribute('aria-pressed', isActive);
  });
}

/* --- Collapse All Cards (shared) --- */

function collapseAllCards(containerId) {
  const cards = document.querySelectorAll(`#${containerId} .claim-card.expanded`);
  cards.forEach(c => {
    c.classList.remove('expanded');
    const toggle = c.querySelector('.claim-toggle');
    if (toggle) {
      toggle.innerHTML = 'Show details &#9662;';
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
  const btn = document.getElementById('toggle-all-btn');
  if (btn) btn.textContent = 'Expand all';
  return cards.length > 0;
}

/* --- Toggle All Claims (shared) --- */

function toggleAllClaims(containerId) {
  const cards = document.querySelectorAll(`#${containerId} .claim-card`);
  const btn = document.getElementById('toggle-all-btn');
  const anyCollapsed = Array.from(cards).some(c => !c.classList.contains('expanded'));
  cards.forEach(c => {
    c.classList.toggle('expanded', anyCollapsed);
    const toggle = c.querySelector('.claim-toggle');
    if (toggle) {
      toggle.innerHTML = anyCollapsed ? 'Hide details &#9652;' : 'Show details &#9662;';
      toggle.setAttribute('aria-expanded', anyCollapsed);
    }
  });
  if (btn) btn.textContent = anyCollapsed ? 'Collapse all' : 'Expand all';
}

/* --- Search Highlight --- */

function highlightMatch(text, query) {
  if (!query) return escapeHtml(text);
  const lower = text.toLowerCase();
  const qLen = query.length;
  let result = '';
  let last = 0;
  let idx = lower.indexOf(query, last);
  while (idx !== -1) {
    result += escapeHtml(text.slice(last, idx));
    result += `<mark class="search-highlight">${escapeHtml(text.slice(idx, idx + qLen))}</mark>`;
    last = idx + qLen;
    idx = lower.indexOf(query, last);
  }
  result += escapeHtml(text.slice(last));
  return result;
}

/* --- Video Card HTML (shared for listings) --- */

function _isRealChannel(ch) {
  return ch && ch !== 'Unknown' && ch.trim() !== '';
}

function buildVideoCardHtml(v, { query, showChannel } = {}) {
  const title = query ? highlightMatch(v.title || v.id, query) : escapeHtml(v.title || v.id);
  const channelHtml = showChannel && _isRealChannel(v.channel)
    ? `<span class="channel-link" onclick="event.preventDefault();event.stopPropagation();window.location.href='/channel/${encodeURIComponent(v.channel)}'">${query ? highlightMatch(v.channel, query) : escapeHtml(v.channel)}</span>`
    : '';
  return `<a class="video-card" href="/video/${v.id}">
    <img class="thumb" src="https://img.youtube.com/vi/${v.id}/hqdefault.jpg" alt="${escapeHtml(v.title || v.id)}" loading="lazy" onerror="this.style.display='none'">
    <h3>${title}</h3>
    <div class="video-card-meta">
      ${channelHtml}
      ${scoreBadgeHtml(v.public_score)}
      <span>${v.claim_count} claim${v.claim_count !== 1 ? 's' : ''}</span>
      <span title="${absoluteDate(v.created_at)}">${formatDate(v.created_at)}</span>
    </div>
  </a>`;
}

/* --- YouTube URL Regex --- */

const YT_URL_REGEX = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/;
