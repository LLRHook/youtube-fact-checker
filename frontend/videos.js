/* YouTube Fact Checker — Public Video Listing */

let allVideos = [];
let totalVideos = 0;
let currentPage = 1;
let totalPages = 1;
const pageLimit = 50;
let searchTimer = null;
let _fetchController = null;

function debouncedApplyFilters() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 200);
}

document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  const initialPage = Math.max(1, parseInt(params.get('page'), 10) || 1);
  loadVideos(initialPage);
});

window.addEventListener('popstate', (e) => {
  const page = (e.state && e.state.page) || 1;
  const skel = document.getElementById('videos-skeleton');
  if (skel) skel.style.display = '';
  document.getElementById('video-grid').innerHTML = '';
  const searchInput = document.getElementById('search-input');
  if (searchInput) { searchInput.value = ''; toggleClearBtn(); }
  loadVideos(page);
});

async function loadVideos(page) {
  if (_fetchController) _fetchController.abort();
  _fetchController = new AbortController();
  const myController = _fetchController;
  try {
    const resp = await fetch(`/api/videos?page=${page}&limit=${pageLimit}`, { signal: myController.signal });
    if (!resp.ok) throw new Error('Failed to load videos');
    const data = await resp.json();
    allVideos = data.items;
    totalVideos = data.total;
    currentPage = data.page;
    totalPages = data.pages;
    // Sync URL if backend clamped the page number
    const expectedUrl = currentPage > 1 ? `?page=${currentPage}` : window.location.pathname;
    if (page !== currentPage) {
      history.replaceState({ page: currentPage }, '', expectedUrl);
    }
    document.title = `${totalVideos} Videos — YouTube Fact Checker`;
    applyFilters();
    renderPagination();
  } catch (err) {
    if (err.name === 'AbortError') return;
    document.getElementById('empty').textContent = 'Error loading videos.';
    document.getElementById('empty').style.display = 'block';
    const pag = document.getElementById('pagination');
    if (pag) pag.innerHTML = '';
  } finally {
    if (_fetchController === myController) {
      const skel = document.getElementById('videos-skeleton');
      if (skel) skel.style.display = 'none';
    }
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
    countEl.textContent = `Showing ${filtered.length} of ${allVideos.length} on this page`;
  } else {
    countEl.textContent = `${totalVideos} video${totalVideos !== 1 ? 's' : ''} checked`;
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
  grid.innerHTML = videos.map(v => buildVideoCardHtml(v, { query, showChannel: true })).join('');
}

function renderPagination() {
  const container = document.getElementById('pagination');
  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = '';
  html += `<button class="page-btn" ${currentPage <= 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})" aria-label="Previous page">&laquo; Prev</button>`;

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
    html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})" aria-label="Page ${i}"${i === currentPage ? ' aria-current="page"' : ''}>${i}</button>`;
  }

  if (endPage < totalPages) {
    if (endPage < totalPages - 1) html += `<span class="page-ellipsis">&hellip;</span>`;
    html += `<button class="page-btn" onclick="goToPage(${totalPages})">${totalPages}</button>`;
  }

  html += `<button class="page-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})" aria-label="Next page">Next &raquo;</button>`;

  container.innerHTML = html;
}

function goToPage(page) {
  if (!page || page < 1 || page > totalPages || page === currentPage) return;
  window.scrollTo({ top: 0, behavior: _prefersReducedMotion.matches ? 'auto' : 'smooth' });
  const skel = document.getElementById('videos-skeleton');
  if (skel) skel.style.display = '';
  document.getElementById('video-grid').innerHTML = '';
  const searchInput = document.getElementById('search-input');
  if (searchInput && searchInput.value) {
    searchInput.value = '';
    toggleClearBtn();
  }
  const url = page > 1 ? `?page=${page}` : window.location.pathname;
  history.pushState({ page }, '', url);
  loadVideos(page);
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
