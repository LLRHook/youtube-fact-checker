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
      container.innerHTML = `<div class="empty-state">
        <p class="empty-heading">Channel not found</p>
        <p class="empty-text">No fact-checked videos for this channel yet.</p>
        <div class="empty-links">
          <a href="/" class="empty-link">Check a video</a>
          <a href="/videos" class="empty-link">Browse videos</a>
        </div>
      </div>`;
      document.title = 'Not Found — YouTube Fact Checker';
      return;
    }
    const data = await resp.json();
    renderChannel(data);
    document.title = `${data.channel} (${data.video_count} video${data.video_count !== 1 ? 's' : ''}, ${Math.round(data.avg_score)}% avg) — YouTube Fact Checker`;
    setMeta('meta[property="og:title"]', `${data.channel} — YouTube Fact Checker`);
    const plural = data.video_count !== 1 ? 's' : '';
    setMeta('meta[property="og:description"]', `${data.video_count} fact-checked video${plural} with ${Math.round(data.avg_score)}% average accuracy.`);
    setMeta('meta[name="description"]', `${data.video_count} fact-checked video${plural} with ${Math.round(data.avg_score)}% average accuracy for ${data.channel}.`);
  } catch (err) {
    container.innerHTML = `<div class="empty-state">
      <p class="empty-heading">Error loading channel</p>
      <p class="empty-text">Something went wrong. Please try again later.</p>
      <a href="/videos" class="empty-link">Browse videos</a>
    </div>`;
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
            ${scoreBadgeHtml(v.public_score)}
            <span>${v.claim_count} claims</span>
            <span title="${absoluteDate(v.created_at)}">${formatDate(v.created_at)}</span>
          </div>
        </a>
      `).join('')
    : '<div class="empty-state">No videos for this channel.</div>';

  const trueCount = data.videos.filter(v => v.public_score >= 75).length;
  const mixedCount = data.videos.filter(v => v.public_score >= 50 && v.public_score < 75).length;
  const falseCount = data.videos.filter(v => v.public_score < 50).length;
  const total = data.videos.length || 1;

  const distBarHtml = data.videos.length > 0 ? `
    <div class="breakdown-bar-container">
      <div class="breakdown-segments">
        ${trueCount ? `<div class="breakdown-seg seg-green" title="${trueCount} true" style="width:${(trueCount/total)*100}%"></div>` : ''}
        ${mixedCount ? `<div class="breakdown-seg seg-yellow" title="${mixedCount} mixed" style="width:${(mixedCount/total)*100}%"></div>` : ''}
        ${falseCount ? `<div class="breakdown-seg seg-red" title="${falseCount} false" style="width:${(falseCount/total)*100}%"></div>` : ''}
      </div>
      <div class="breakdown-legend">
        ${trueCount ? `<span class="legend-item"><span class="legend-dot dot-green"></span>${trueCount} true</span>` : ''}
        ${mixedCount ? `<span class="legend-item"><span class="legend-dot dot-yellow"></span>${mixedCount} mixed</span>` : ''}
        ${falseCount ? `<span class="legend-item"><span class="legend-dot dot-red"></span>${falseCount} false</span>` : ''}
      </div>
    </div>
  ` : '';

  container.innerHTML = `
    <div class="channel-header">
      <h1>${escapeHtml(data.channel)}</h1>
      <div class="channel-stats">
        <span><span class="stat-value">${data.video_count}</span> videos</span>
        <span>Avg accuracy: <span class="stat-value" style="color:${scoreColor(data.avg_score)}">${Math.round(data.avg_score)}%</span></span>
      </div>
    </div>
    ${distBarHtml}
    <div class="video-grid">${videosHtml}</div>
  `;
}

