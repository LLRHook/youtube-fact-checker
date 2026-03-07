/* YouTube Fact Checker — Shared Utilities */

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'Z');
  const now = new Date();
  const diffMs = now - d;
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
  return new Date(dateStr + 'Z').toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

function formatTimestamp(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
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
      ${trueCount ? `<div class="breakdown-seg seg-green" title="${trueCount} true" style="width:${(trueCount/total)*100}%"></div>` : ''}
      ${mixedCount ? `<div class="breakdown-seg seg-yellow" title="${mixedCount} mixed" style="width:${(mixedCount/total)*100}%"></div>` : ''}
      ${falseCount ? `<div class="breakdown-seg seg-red" title="${falseCount} false" style="width:${(falseCount/total)*100}%"></div>` : ''}
      ${opinions.length ? `<div class="breakdown-seg seg-gray" title="${opinions.length} opinion" style="width:${(opinions.length/total)*100}%"></div>` : ''}
    </div>
    <div class="breakdown-legend">
      ${trueCount ? `<span class="legend-item"><span class="legend-dot dot-green"></span>${trueCount} true</span>` : ''}
      ${mixedCount ? `<span class="legend-item"><span class="legend-dot dot-yellow"></span>${mixedCount} mixed</span>` : ''}
      ${falseCount ? `<span class="legend-item"><span class="legend-dot dot-red"></span>${falseCount} false</span>` : ''}
      ${opinions.length ? `<span class="legend-item"><span class="legend-dot dot-gray"></span>${opinions.length} opinion</span>` : ''}
    </div>
  `;
}

/* --- Theme --- */

function initTheme() {
  const saved = localStorage.getItem('theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
  updateToggleIcon();
  updateThemeMeta();
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateToggleIcon();
  updateThemeMeta();
}

function updateToggleIcon() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  const theme = document.documentElement.getAttribute('data-theme');
  btn.innerHTML = theme === 'light' ? '&#9790;' : '&#9728;';
  btn.title = theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode';
}

function updateThemeMeta() {
  const meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) return;
  const theme = document.documentElement.getAttribute('data-theme');
  meta.setAttribute('content', theme === 'light' ? '#f5f5f7' : '#0f0f0f');
}

initTheme();

/* --- Claim Card Interactions --- */

function toggleClaim(btn) {
  const card = btn.closest('.claim-card');
  card.classList.toggle('expanded');
  btn.innerHTML = card.classList.contains('expanded')
    ? 'Hide details &#9652;'
    : 'Show details &#9662;';
}

function addCardClickListeners(containerId) {
  document.querySelectorAll(`#${containerId} .claim-card`).forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
      toggleClaim(card.querySelector('.claim-toggle'));
    });
  });
}

/* --- Filter Counts --- */

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

/* --- Back to Top --- */

function initBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  window.addEventListener('scroll', () => {
    btn.classList.toggle('visible', window.scrollY > 400);
  }, { passive: true });
}

initBackToTop();

/* --- Collapse All Cards (shared) --- */

function collapseAllCards(containerId) {
  const cards = document.querySelectorAll(`#${containerId} .claim-card.expanded`);
  cards.forEach(c => {
    c.classList.remove('expanded');
    const toggle = c.querySelector('.claim-toggle');
    if (toggle) toggle.innerHTML = 'Show details &#9662;';
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
    if (toggle) toggle.innerHTML = anyCollapsed ? 'Hide details &#9652;' : 'Show details &#9662;';
  });
  btn.textContent = anyCollapsed ? 'Collapse all' : 'Expand all';
}

/* --- YouTube URL Regex --- */

const YT_URL_REGEX = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/;
