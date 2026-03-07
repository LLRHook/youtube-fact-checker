/* YouTube Fact Checker — Public Video Listing */

let allVideos = [];
let searchTimer = null;

function debouncedApplyFilters() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 200);
}

document.addEventListener('DOMContentLoaded', () => {
  loadVideos();
});

async function loadVideos() {
  try {
    const resp = await fetch('/api/videos');
    if (!resp.ok) throw new Error('Failed to load videos');
    allVideos = await resp.json();
    const skel = document.getElementById('videos-skeleton');
    if (skel) skel.style.display = 'none';
    applyFilters();
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
    countEl.textContent = `${filtered.length} of ${allVideos.length} videos`;
  } else {
    countEl.textContent = `${allVideos.length} videos`;
  }

  renderGrid(filtered);
}

function renderGrid(videos) {
  const grid = document.getElementById('video-grid');
  const empty = document.getElementById('empty');

  if (videos.length === 0) {
    grid.innerHTML = '';
    if (allVideos.length === 0) {
      empty.style.display = 'block';
    } else {
      empty.style.display = 'none';
      grid.innerHTML = '<div style="text-align: center; padding: 2rem; grid-column: 1/-1;"><p style="color: var(--text-muted); margin-bottom: 0.75rem;">No matching videos found.</p><button onclick="document.getElementById(\'search-input\').value=\'\';applyFilters();" style="background:var(--surface);color:var(--accent);border:1px solid var(--border);border-radius:8px;padding:0.5rem 1rem;cursor:pointer;font-size:0.85rem;">Clear search</button></div>';
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
        <span>${formatDate(v.created_at)}</span>
      </div>
    </a>
  `).join('');
}

function scoreClass(score) {
  if (score >= 75) return 'score-green';
  if (score >= 50) return 'score-yellow';
  return 'score-red';
}

function verdictLabel(score) {
  if (score >= 75) return 'True';
  if (score >= 50) return 'Mixed';
  return 'False';
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

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function highlightMatch(text, query) {
  const escaped = escapeHtml(text);
  if (!query) return escaped;
  const idx = text.toLowerCase().indexOf(query);
  if (idx === -1) return escaped;
  const before = escapeHtml(text.slice(0, idx));
  const match = escapeHtml(text.slice(idx, idx + query.length));
  const after = escapeHtml(text.slice(idx + query.length));
  return `${before}<mark style="background:rgba(108,99,255,0.3);color:var(--text);border-radius:2px;padding:0 1px;">${match}</mark>${after}`;
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
      input.focus();
    } else {
      input.blur();
    }
  }
});
