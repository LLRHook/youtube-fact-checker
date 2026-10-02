'use strict';
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ICONS = {
  check:'<path d="m4 8 3 3 5-6"/>', circle:'<circle cx="8" cy="8" r="6"/><path d="m5 8 2 2 4-4"/>',
  mixed:'<circle cx="8" cy="8" r="6"/><path d="M8 2v12M4 8h3"/>', crossCircle:'<circle cx="8" cy="8" r="6"/><path d="m6 6 4 4m0-4-4 4"/>',
  cross:'<path d="m4 4 8 8m0-8-8 8"/>', question:'<circle cx="8" cy="8" r="6"/><path d="M6 6a2 2 0 1 1 3 1.7L8 9M8 11h.01"/>',
  speech:'<path d="M3 3h10v8H7l-4 3V3Z"/>', warning:'<path d="m8 2 7 12H1L8 2ZM8 6v4m0 2h.01"/>',
  link:'<path d="m6 10 4-4M6 5H4a3 3 0 0 0 0 6h2m4-6h2a3 3 0 0 0 0-6h-2"/>', transcript:'<path d="M3 2h10v12H3ZM5 5h6M5 8h6M5 11h4"/>', search:'<circle cx="7" cy="7" r="4"/><path d="m10 10 4 4"/>'
};
function icon(name) { return `<svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ICONS.check}</svg>`; }
const VERDICTS = {
  true:{label:'True',icon:'check',meaning:'Accurate, nothing significant missing.'},
  mostly_true:{label:'Mostly true',icon:'circle',meaning:'Accurate but needs clarification or a minor detail is off.'},
  mixed:{label:'Mixed',icon:'mixed',meaning:'Partly accurate and partly inaccurate, or missing context that changes the meaning.'},
  mostly_false:{label:'Mostly false',icon:'crossCircle',meaning:'An element of truth but the core is wrong or misleading.'},
  false:{label:'False',icon:'cross',meaning:'Contradicted by reliable evidence.'},
  unverifiable:{label:'Unverified',icon:'question',meaning:'Evidence insufficient or reliable sources conflict.'},
  opinion:{label:'Opinion',icon:'speech',meaning:'A value judgment or prediction, not checkable.'}
};
function verdictPill(verdict,count='') { const v=VERDICTS[verdict] || VERDICTS.unverifiable; return `<span class="pill v-${VERDICTS[verdict] ? verdict : 'unverifiable'}">${icon(v.icon)}${v.label}${count === '' ? '' : ` <span class="pill-count">${escapeHtml(count)}</span>`}</span>`; }
function scoreColor(s) { return s == null ? 'unverifiable' : s>=80 ? 'true' : s>=60 ? 'mostly_true' : s>=40 ? 'mixed' : s>=20 ? 'mostly_false' : 'false'; }
function scoreRing(score,small=false) {
  const value=score == null ? '—' : Math.round(score);
  return `<div class="score-block ${small ? 'small' : ''}"><div class="score-ring v-${scoreColor(score)}"><svg viewBox="0 0 120 120" role="img" aria-label="Accuracy score: ${value}${score == null ? '' : ' out of 100'}"><circle class="ring-track" cx="60" cy="60" r="52"/><circle class="ring-value" cx="60" cy="60" r="52" pathLength="100" stroke-dasharray="${score == null ? 0 : Math.max(0,Math.min(100,score))} 100" transform="rotate(-90 60 60)"/></svg><strong>${value}</strong></div><span class="score-caption" title="Confidence-weighted average across checkable claims">Accuracy score</span></div>`;
}
function verdictBar(counts={}) { const total=Object.values(counts).reduce((a,b)=>a+b,0); return `<div class="verdict-bar" role="img" aria-label="Verdict distribution: ${escapeHtml(Object.entries(counts).map(([v,n])=>`${n} ${VERDICTS[v]?.label || v}`).join(', '))}">${Object.keys(VERDICTS).filter(v=>counts[v]).map(v=>`<span class="v-${v}" style="flex:${Number(counts[v])/(total || 1)}" aria-label="${Number(counts[v])} ${VERDICTS[v].label}"></span>`).join('')}</div>`; }
async function api(path,{method='GET',body,timeoutMs=15000}={}) {
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs);
  try { const response=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body===undefined ? undefined : JSON.stringify(body),signal:controller.signal});
    const data=response.status===204 ? null : await response.json();
    if (!response.ok) { const error=new Error(typeof data.detail==='string' ? data.detail : 'This request could not be completed.'); error.status=response.status; throw error; } return data;
  } catch(error) { if(error.name==='AbortError') throw new Error('The request timed out. Please try again.'); throw error; } finally { clearTimeout(timer); }
}
function formatTimestamp(seconds) { const s=Math.max(0,Math.floor(Number(seconds)||0)),h=Math.floor(s/3600),m=Math.floor(s%3600/60); return `${h ? h+':'+String(m).padStart(2,'0') : m}:${String(s%60).padStart(2,'0')}`; }
function formatDuration(s) { return formatTimestamp(s); }
function relativeDate(value) { if(!value) return ''; const date=new Date(value.includes('T') ? value : value.replace(' ','T')+'Z'); if(Number.isNaN(+date)) return ''; const days=Math.max(0,Math.floor((Date.now()-date)/86400000)); return days===0 ? 'today' : days===1 ? 'yesterday' : days<30 ? `${days} days ago` : date.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'}); }
const YT_URL_REGEX=/^[\w-]{11}$/;
function extractVideoId(value) {
  value=value.trim(); if(YT_URL_REGEX.test(value)) return value;
  try { const url=new URL(/^https?:\/\//i.test(value) ? value : `https://${value}`); if(!['http:','https:'].includes(url.protocol)) return null; const host=url.hostname.toLowerCase(); let id;
    if(host==='youtu.be') id=url.pathname.split('/')[1];
    else if(['youtube.com','www.youtube.com','m.youtube.com'].includes(host)) id=url.pathname==='/watch' ? url.searchParams.get('v') : /^\/(shorts|embed|live)\//.test(url.pathname) ? url.pathname.split('/')[2] : null;
    return id && YT_URL_REGEX.test(id) ? id : null;
  } catch(_) { return null; }
}
function toast(message) { const el=document.getElementById('toast'); el.textContent=message; el.classList.add('visible'); clearTimeout(toast.timer); toast.timer=setTimeout(()=>el.classList.remove('visible'),3500); }
async function copyText(text) { if(navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return; } const field=document.createElement('textarea'); field.value=text; field.className='copy-field'; document.body.append(field); field.select(); const ok=document.execCommand('copy'); field.remove(); if(!ok) throw new Error('Copy is unavailable in this browser.'); }
function imageFallback(root=document) { root.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{ img.hidden=true; img.parentElement.classList.add('image-failed'); })); }
function videoCard(v) { return `<article class="video-card card"><div class="thumbnail"><span class="thumbnail-fallback" aria-hidden="true">${icon('transcript')}<span>Video report</span></span><img src="https://i.ytimg.com/vi/${encodeURIComponent(v.id)}/hqdefault.jpg" alt="" width="480" height="270" loading="lazy"><span class="score-badge v-${scoreColor(v.public_score)}">${v.public_score==null ? '—' : escapeHtml(v.public_score)}<small> / 100</small></span></div><div class="video-card-content"><h3><a class="stretched-link" href="/video/${encodeURIComponent(v.id)}">${escapeHtml(v.title || 'Untitled video')}</a></h3>${v.channel ? `<a class="channel-link" href="/channel/${encodeURIComponent(v.channel)}">${escapeHtml(v.channel)}</a>` : ''}<div class="card-meta"><span>${escapeHtml(relativeDate(v.created_at))}</span><span>${Number(v.claim_count)||0} claims</span></div>${verdictBar(v.verdict_counts)}</div></article>`; }
function skeletonCards(n=3) { return Array.from({length:n},()=>'<div class="card skeleton-card" aria-hidden="true"><div class="skeleton skeleton-thumb"></div><div class="skeleton-lines"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div></div>').join(''); }
function emptyState(title,text,action='') { return `<div class="empty-state card">${icon('question')}<h2>${escapeHtml(title)}</h2><p>${escapeHtml(text)}</p>${action}</div>`; }
function isTyping(target) { return target.matches('input, textarea, select, [contenteditable="true"]'); }
document.querySelectorAll('[data-verdict-legend]').forEach(el=>{ el.innerHTML=Object.entries(VERDICTS).map(([v,m])=>`<div class="legend-row">${verdictPill(v)}<p>${m.meaning}</p></div>`).join(''); });
document.querySelectorAll('[data-step-icon]').forEach(el=>{ el.innerHTML=icon(el.dataset.stepIcon); });
const themeToggle=document.getElementById('theme-toggle');
function syncThemeButton() { const dark=document.documentElement.dataset.theme==='dark'; themeToggle.setAttribute('aria-label',`Switch to ${dark ? 'light' : 'dark'} theme`); themeToggle.setAttribute('aria-pressed',String(dark)); }
syncThemeButton();
themeToggle.addEventListener('click',()=>{ document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark' ? 'light' : 'dark'; try { localStorage.setItem('theme',document.documentElement.dataset.theme); } catch(_) {} syncThemeButton(); });
document.querySelectorAll('.site-nav a').forEach(link=>{ if(link.pathname===location.pathname) link.setAttribute('aria-current','page'); });
