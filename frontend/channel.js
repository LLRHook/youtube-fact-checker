/* YouTube Fact Checker — Channel Page */

document.addEventListener('DOMContentLoaded', () => {
  const parts = window.location.pathname.split('/');
  const channelName = decodeURIComponent(parts[parts.length - 1]);
  if (channelName) loadChannel(channelName);
});

async function loadChannel(channelName) {
  const container = document.getElementById('content');
  try {
    const resp = await fetch(`/api/channels/${encodeURIComponent(channelName)}`);
    if (!resp.ok) {
      container.innerHTML = '<div class="empty-state">Channel not found.</div>';
      return;
    }
    const data = await resp.json();
    renderChannel(data);
    document.title = `${data.channel} — YouTube Fact Checker`;
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) ogTitle.setAttribute('content', `${data.channel} — YouTube Fact Checker`);
  } catch (err) {
    container.innerHTML = '<div class="empty-state">Error loading channel.</div>';
  }
}

function renderChannel(data) {
  const container = document.getElementById('content');

  const videosHtml = data.videos.length > 0
    ? data.videos.map(v => `
        <a class="video-card" href="/video/${v.id}">
          <img class="thumb" src="https://img.youtube.com/vi/${v.id}/hqdefault.jpg" alt="${escapeHtml(v.title || v.id)}" loading="lazy">
          <h3>${escapeHtml(v.title || v.id)}</h3>
          <div class="video-card-meta">
            <span class="score-badge ${scoreClass(v.public_score)}" title="Accuracy score: ${v.public_score}% — ${verdictLabel(v.public_score)}">${verdictLabel(v.public_score)} · ${v.public_score}%</span>
            <span>${v.claim_count} claims</span>
            <span>${formatDate(v.created_at)}</span>
          </div>
        </a>
      `).join('')
    : '<div class="empty-state">No videos for this channel.</div>';

  container.innerHTML = `
    <div class="channel-header">
      <h1>${escapeHtml(data.channel)}</h1>
      <div class="channel-stats">
        <span><span class="stat-value">${data.video_count}</span> videos</span>
        <span>Avg accuracy: <span class="stat-value" style="color:${scoreColor(data.avg_score)}">${Math.round(data.avg_score)}%</span></span>
      </div>
    </div>
    <div class="video-grid">${videosHtml}</div>
  `;
}

function scoreColor(score) {
  if (score >= 75) return '#2ed573';
  if (score >= 50) return '#ffa502';
  return '#ff4757';
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
