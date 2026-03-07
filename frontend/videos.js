/* YouTube Fact Checker — Public Video Listing */

document.addEventListener('DOMContentLoaded', () => {
  loadVideos();
});

async function loadVideos() {
  try {
    const resp = await fetch('/api/videos');
    if (!resp.ok) throw new Error('Failed to load videos');
    const videos = await resp.json();
    renderGrid(videos);
  } catch (err) {
    document.getElementById('empty').textContent = 'Error loading videos.';
    document.getElementById('empty').style.display = 'block';
  }
}

function renderGrid(videos) {
  const grid = document.getElementById('video-grid');
  const empty = document.getElementById('empty');

  if (videos.length === 0) {
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  grid.innerHTML = videos.map(v => `
    <a class="video-card" href="/video/${v.id}">
      <img class="thumb" src="https://img.youtube.com/vi/${v.id}/hqdefault.jpg" alt="" loading="lazy">
      <h3>${escapeHtml(v.title || v.id)}</h3>
      <div class="video-card-meta">
        <span class="channel-link" onclick="event.preventDefault();event.stopPropagation();location.href='/channel/${encodeURIComponent(v.channel)}'">
          ${escapeHtml(v.channel || 'Unknown')}
        </span>
        <span class="score-badge ${scoreClass(v.public_score)}">${v.public_score}%</span>
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
