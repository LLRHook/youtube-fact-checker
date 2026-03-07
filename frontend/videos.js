/* YouTube Fact Checker — Public Video Listing */

let allVideos = [];
let totalVideos = 0;
let currentPage = 1;
let totalPages = 1;
let pageLimit = 50;
let searchTimer = null;

function debouncedApplyFilters() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 200);
}

document.addEventListener('DOMContentLoaded', () => {
  loadVideos(1);
});

async function loadVideos(page) {
  try {
    const resp = await fetch(`/api/videos?page=${page}&limit=${pageLimit}`);
    if (!resp.ok) throw new Error('Failed to load videos');
    const data = await resp.json();
    allVideos = data.items;
    totalVideos = data.total;
    currentPage = data.page;
    totalPages = data.pages;
    const skel = document.getElementById('videos-skeleton');
    if (skel) skel.style.display = 'none';
    document.title = `${totalVideos} Videos — YouTube Fact Checker`;
    applyFilters();
    renderPagination();
  } catch (err) {
    const skel = document.getElementById('videos-skeleton');
    if (skel) skel.style.display = 'none';
    document.getElementById('empty').textContent = 'Error loading videos.';
    document.getElementById('empty').style.display = 'block';
  }
}

function applyFilters() {
  const query = document.getElementById('search-input').value.toLowerCase().trim();
  const sort = document.getElementById('sort-select').value;

  let filtered = allVideos;

  if (query) {
    filtered = filtered.filter(v =>
      (v.title || '').toLowerCase().includes(query) ||
      (v.channel || '').toLowerCase().includes(query)
    );
  }

  filtered = [...filtered].sort((a, b) => {
    switch (sort) {
      case 'date-desc': return (b.created_at || '').localeCompare(a.created_at || '');
      case 'date-asc': return (a.created_at || '').localeCompare(b.created_at || '');
      case 'score-desc': return b.public_score - a.public_score;
      case 'score-asc': return a.public_score - b.public_score;
      case 'claims-desc': return b.claim_count - a.claim_count;
      default: return 0;
    }
  });

  const countEl = document.getElementById('results-count');
  if (query) {
    countEl.textContent = `${filtered.length} of ${allVideos.length} on this page (${totalVideos} total)`;
  } else {
    countEl.textContent = `${totalVideos} videos`;
  }

  renderGrid(filtered);
}

function renderGrid(videos) {
  const grid = document.getElementById('video-grid');
  const empty = document.getElementById('empty');

  if (videos.length === 0) {
    grid.innerHTML = '';
    if (allVideos.length === 0 && totalVideos === 0) {
      empty.style.display = 'block';
    } else {
      empty.style.display = 'none';
      grid.innerHTML = '<div class="no-results"><p>No matching videos found.</p><button class="clear-search-btn" onclick="document.getElementById(\'search-input\').value=\'\';applyFilters();">Clear search</button></div>';
    }
    return;
  }
  empty.style.display = 'none';

  const query = document.getElementById('search-input').value.toLowerCase().trim();
  grid.innerHTML = videos.map(v => `
    <a class="video-card" href="/video/${v.id}">
      <img class="thumb" src="https://img.youtube.com/vi/${v.id}/hqdefault.jpg" alt="${escapeHtml(v.title || v.id)}" loading="lazy">
      <h3>${highlightMatch(v.title || v.id, query)}</h3>
      <div class="video-card-meta">
        <span class="channel-link" onclick="event.preventDefault();event.stopPropagation();location.href='/channel/${encodeURIComponent(v.channel)}'">
          ${highlightMatch(v.channel || 'Unknown', query)}
        </span>
        <span class="score-badge ${scoreClass(v.public_score)}" title="Accuracy score: ${v.public_score}% — ${verdictLabel(v.public_score)}">${verdictLabel(v.public_score)} · ${v.public_score}%</span>
        <span>${v.claim_count} claims</span>
        <span title="${absoluteDate(v.created_at)}">${formatDate(v.created_at)}</span>
      </div>
    </a>
  `).join('');
}

function renderPagination() {
  const container = document.getElementById('pagination');
  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = '';
  html += `<button class="page-btn" ${currentPage <= 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">&laquo; Prev</button>`;

  const maxButtons = 5;
  let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
  let endPage = Math.min(totalPages, startPage + maxButtons - 1);
  if (endPage - startPage < maxButtons - 1) {
    startPage = Math.max(1, endPage - maxButtons + 1);
  }

  if (startPage > 1) {
    html += `<button class="page-btn" onclick="goToPage(1)">1</button>`;
    if (startPage > 2) html += `<span class="page-ellipsis">&hellip;</span>`;
  }

  for (let i = startPage; i <= endPage; i++) {
    html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
  }

  if (endPage < totalPages) {
    if (endPage < totalPages - 1) html += `<span class="page-ellipsis">&hellip;</span>`;
    html += `<button class="page-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
  }

  html += `<button class="page-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">Next &raquo;</button>`;

  container.innerHTML = html;
}

function goToPage(page) {
  if (page < 1 || page > totalPages || page === currentPage) return;
  window.scrollTo({ top: 0, behavior: 'smooth' });
  const skel = document.getElementById('videos-skeleton');
  if (skel) skel.style.display = '';
  document.getElementById('video-grid').innerHTML = '';
  loadVideos(page);
}

function highlightMatch(text, query) {
  const escaped = escapeHtml(text);
  if (!query) return escaped;
  const idx = text.toLowerCase().indexOf(query);
  if (idx === -1) return escaped;
  const before = escapeHtml(text.slice(0, idx));
  const match = escapeHtml(text.slice(idx, idx + query.length));
  const after = escapeHtml(text.slice(idx + query.length));
  return `${before}<mark class="search-highlight">${match}</mark>${after}`;
}

function toggleClearBtn() {
  const btn = document.getElementById('search-clear');
  if (btn) btn.style.display = document.getElementById('search-input').value ? 'block' : 'none';
}

document.addEventListener('keydown', (e) => {
  if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT')) return;
    e.preventDefault();
    document.getElementById('search-input').focus();
  }
  if (e.key === 'Escape') {
    const input = document.getElementById('search-input');
    if (input.value) {
      input.value = '';
      applyFilters();
      toggleClearBtn();
      input.focus();
    } else {
      input.blur();
    }
  }
});
