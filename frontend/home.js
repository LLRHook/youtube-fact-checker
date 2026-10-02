'use strict';
const urlInput=document.getElementById('url-input'),errorLine=document.getElementById('input-error'),preview=document.getElementById('url-preview');
urlInput.addEventListener('input',()=>{ errorLine.textContent=''; urlInput.removeAttribute('aria-invalid'); const id=extractVideoId(urlInput.value); preview.hidden=!id; if(id) { preview.innerHTML=`<div class="thumbnail"><img src="https://i.ytimg.com/vi/${id}/mqdefault.jpg" width="120" height="68" alt="" loading="lazy"></div><div><strong>Ready to check</strong><p>${id}</p></div>`; imageFallback(preview); } });
const pasteButton=document.getElementById('paste-button'); pasteButton.hidden=!navigator.clipboard?.readText;
pasteButton.addEventListener('click',async()=>{ try { urlInput.value=await navigator.clipboard.readText(); urlInput.dispatchEvent(new Event('input')); urlInput.focus(); } catch(_) { toast('Clipboard access is unavailable. Paste the link into the field.'); } });
document.getElementById('check-form').addEventListener('submit',async event=>{
  event.preventDefault(); const id=extractVideoId(urlInput.value);
  if(!id) { errorLine.textContent='Enter a valid YouTube link or an 11-character video ID.'; urlInput.setAttribute('aria-invalid','true'); urlInput.focus(); return; }
  const button=document.getElementById('check-button'); button.disabled=true; button.textContent='Starting…';
  try { const result=await api('/api/check',{method:'POST',body:{youtube_url:`https://www.youtube.com/watch?v=${id}`}}); location.assign(`/video/${encodeURIComponent(result.task_id)}`); } catch(error) { errorLine.textContent=error.message; } finally { button.disabled=false; button.textContent='Check video'; }
});
document.addEventListener('keydown',e=>{ if(e.key==='/' && !isTyping(e.target)) { e.preventDefault(); urlInput.focus(); } });
(async()=>{ try { const data=await api('/api/videos?limit=6'),section=document.getElementById('recent'); if(!data.items.length) { section.hidden=true; return; } document.getElementById('recent-grid').innerHTML=data.items.map(videoCard).join(''); imageFallback(section); } catch(_) { document.getElementById('recent').hidden=true; } })();
(async()=>{ try { const data=await api('/api/stats'),strip=document.getElementById('stats'); strip.innerHTML=[['video_count','videos checked'],['claim_count','claims checked'],['channel_count','channels']].map(([key,label])=>`<div><strong>${Number(data[key]).toLocaleString()}</strong><span>${label}</span></div>`).join(''); strip.hidden=false; } catch(_) {} })();
