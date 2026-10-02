'use strict';
(async()=>{
  const root=document.getElementById('channel-content');
  try { const name=decodeURIComponent(location.pathname.split('/').pop()),data=await api(`/api/channels/${encodeURIComponent(name)}`); document.title=`${data.channel} — YouTube Fact Checker`;
    root.innerHTML=`<div class="channel-heading"><div><p class="eyebrow">Channel reports</p><h1>${escapeHtml(data.channel)}</h1><p class="muted">${Number(data.video_count)} checked video${data.video_count===1 ? '' : 's'}</p></div>${scoreRing(data.avg_score,true)}</div><div class="video-grid">${data.videos.map(videoCard).join('')}</div>`; imageFallback(root);
  } catch(error) { root.innerHTML=emptyState(error.status===404 ? 'No reports for this channel yet' : 'Could not load this channel',error.status===404 ? 'Check a video to start a channel report.' : error.message,'<a class="button primary" href="/">Check a video</a>'); }
})();
