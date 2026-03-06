/* YouTube Fact Checker — Admin Review Page */

let allVideos = [];
let currentFilter = 'all';
let currentVideoId = null;

// --- Init ---

document.addEventListener('DOMContentLoaded', () => {
  loadVideos();
});

// --- Video List ---

async function loadVideos() {
  try {
    const resp = await fetch('/api/admin/videos');
    if (!resp.ok) throw new Error('Failed to load videos');
    allVideos = await resp.json();
    renderVideoList();
  } catch (err) {
    document.getElementById('list-empty').textContent = 'Error loading videos.';
    document.getElementById('list-empty').style.display = 'block';
  }
}

function renderVideoList() {
  const filtered = currentFilter === 'all'
    ? allVideos
    : allVideos.filter(v => v.approval_status === currentFilter);

  const tbody = document.getElementById('video-list');
  const empty = document.getElementById('list-empty');

  if (filtered.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  tbody.innerHTML = filtered.map(v => `
    <tr onclick="openVideo('${v.id}')">
      <td>${escapeHtml(v.title || v.id)}</td>
      <td>${escapeHtml(v.channel || '-')}</td>
      <td><span class="score-sm ${scoreClass(v.overall_truth_percentage)}">${v.overall_truth_percentage}%</span></td>
      <td>${v.claim_count}</td>
      <td><span class="status-badge status-${v.status}">${v.status}</span></td>
      <td><span class="status-badge status-${v.approval_status}">${v.approval_status}</span></td>
      <td>${formatDate(v.created_at)}</td>
    </tr>
  `).join('');
}

function filterTab(tab) {
  currentFilter = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.tab-btn[data-tab="${tab}"]`).classList.add('active');
  renderVideoList();
}

// --- Video Detail ---

async function openVideo(videoId) {
  currentVideoId = videoId;
  try {
    const resp = await fetch(`/api/admin/videos/${videoId}`);
    if (!resp.ok) throw new Error('Failed to load video');
    const video = await resp.json();
    renderDetail(video);
    document.getElementById('list-view').style.display = 'none';
    document.getElementById('detail-view').style.display = 'block';
  } catch (err) {
    alert('Error loading video details.');
  }
}

function renderDetail(video) {
  document.getElementById('detail-title').textContent = video.title || video.id;
  document.getElementById('detail-channel').textContent = video.channel || '';
  document.getElementById('detail-score').textContent = `Score: ${video.overall_truth_percentage}%`;

  const mins = Math.floor(video.duration_seconds / 60);
  const secs = Math.round(video.duration_seconds % 60);
  document.getElementById('detail-duration').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
  document.getElementById('detail-time').textContent = `Processed in ${video.processing_time_seconds}s`;
  document.getElementById('detail-date').textContent = formatDate(video.created_at);

  renderDetailClaims(video.claims, video.id);
}

function renderDetailClaims(claims, videoId) {
  const container = document.getElementById('detail-claims');

  if (!claims || claims.length === 0) {
    container.innerHTML = '<p class="empty-state">No claims for this video.</p>';
    return;
  }

  container.innerHTML = claims.map(c => {
    const badgeClass = getBadgeClass(c.truth_percentage, c.category);
    const badgeText = c.category === 'opinion' ? 'Opinion' : `${c.truth_percentage}%`;
    const ts = formatTimestamp(c.timestamp_seconds);
    const ytLink = `https://youtube.com/watch?v=${videoId}&t=${Math.floor(c.timestamp_seconds)}`;
    const attrClass = c.attributed_to_creator ? '' : ' not-creator';

    let sourcesHtml = '';
    if (c.sources && c.sources.length > 0) {
      sourcesHtml = '<div class="claim-sources">' +
        c.sources.map(s =>
          `<a href="${s.url}" target="_blank" rel="noopener" class="source-link">${escapeHtml(s.title)}</a>`
        ).join('') + '</div>';
    }

    return `
      <div class="admin-claim${attrClass}" data-claim-id="${c.id}">
        <div class="admin-claim-header">
          <span class="admin-claim-text">${escapeHtml(c.text)}</span>
          <span class="claim-badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="admin-claim-meta">
          <span class="category-tag">${c.category}</span>
          <a href="${ytLink}" target="_blank">${ts}</a>
          ${c.confidence ? `<span>Confidence: ${Math.round(c.confidence * 100)}%</span>` : ''}
        </div>
        <button class="claim-toggle" onclick="toggleAdminClaim(this)">Show details &#9662;</button>
        <div class="claim-reasoning">${escapeHtml(c.reasoning)}</div>
        ${sourcesHtml}
        <div class="toggle-row">
          <span class="toggle-label">Attributed to creator</span>
          <div class="toggle-switch${c.attributed_to_creator ? ' on' : ''}"
               onclick="toggleAttribution(${c.id}, this)"></div>
        </div>
      </div>
    `;
  }).join('');
}

function toggleAdminClaim(btn) {
  const card = btn.closest('.admin-claim');
  card.classList.toggle('expanded');
  btn.innerHTML = card.classList.contains('expanded')
    ? 'Hide details &#9652;'
    : 'Show details &#9662;';
}

async function toggleAttribution(claimId, el) {
  const isOn = el.classList.contains('on');
  const newValue = !isOn;

  try {
    const resp = await fetch(`/api/admin/claims/${claimId}/attribution`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attributed_to_creator: newValue }),
    });
    if (!resp.ok) throw new Error('Failed to update');

    el.classList.toggle('on', newValue);
    const card = el.closest('.admin-claim');
    card.classList.toggle('not-creator', !newValue);
  } catch (err) {
    alert('Failed to update attribution.');
  }
}

async function setApproval(status) {
  if (!currentVideoId) return;
  try {
    const resp = await fetch(`/api/admin/videos/${currentVideoId}/approval`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_status: status }),
    });
    if (!resp.ok) throw new Error('Failed to update');

    // Update local data
    const idx = allVideos.findIndex(v => v.id === currentVideoId);
    if (idx !== -1) allVideos[idx].approval_status = status;

    alert(`Video ${status}.`);
  } catch (err) {
    alert('Failed to update approval status.');
  }
}

function showList() {
  document.getElementById('detail-view').style.display = 'none';
  document.getElementById('list-view').style.display = 'block';
  currentVideoId = null;
  renderVideoList();
}

// --- Helpers ---

function scoreClass(score) {
  if (score >= 75) return 'score-green';
  if (score >= 50) return 'score-yellow';
  return 'score-red';
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
  if (!dateStr) return '-';
  const d = new Date(dateStr + 'Z');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
