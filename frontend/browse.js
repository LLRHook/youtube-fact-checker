'use strict';
const browseSearch=document.getElementById('browse-search'),browseSort=document.getElementById('browse-sort'),grid=document.getElementById('video-grid');
let browsePage=1,browsePages=1,browseRequest=0,searchTimer;
function readBrowseURL() { const p=new URLSearchParams(location.search); browseSearch.value=p.get('q')||''; browseSort.value=['newest','highest','lowest'].includes(p.get('sort')) ? p.get('sort') : 'newest'; browsePage=Math.max(1,parseInt(p.get('page'),10)||1); }
async function loadBrowse() {
  const request=++browseRequest,q=browseSearch.value.trim(),params=new URLSearchParams({q,sort:browseSort.value,page:String(browsePage)});
  history.replaceState(null,'',`${location.pathname}?${params}`); grid.innerHTML=skeletonCards(6); grid.setAttribute('aria-busy','true');
  try { const data=await api(`/api/videos?${params}&limit=12`); if(request!==browseRequest) return;
    browsePage=data.page; browsePages=data.pages; params.set('page',String(browsePage)); history.replaceState(null,'',`${location.pathname}?${params}`);
    document.getElementById('video-count').textContent=`${data.total} videos`;
    grid.innerHTML=data.items.length ? data.items.map(videoCard).join('') : emptyState(q ? `No videos match '${q}'` : 'No checked videos yet','Try another search or check a video.','<button id="clear-search" class="button secondary">Clear search</button>');
    imageFallback(grid); document.getElementById('clear-search')?.addEventListener('click',()=>{ browseSearch.value=''; browsePage=1; loadBrowse(); });
    document.getElementById('page-label').textContent=`Page ${browsePage} of ${browsePages}`;
    document.getElementById('prev-page').disabled=browsePage<=1; document.getElementById('next-page').disabled=browsePage>=browsePages;
  } catch(error) { if(request!==browseRequest) return; grid.innerHTML=emptyState('Could not load videos',error.message,'<button id="retry-browse" class="button primary">Retry</button>'); document.getElementById('retry-browse').addEventListener('click',loadBrowse); } finally { if(request===browseRequest) grid.setAttribute('aria-busy','false'); }
}
browseSearch.addEventListener('input',()=>{ clearTimeout(searchTimer); searchTimer=setTimeout(()=>{ browsePage=1; loadBrowse(); },300); });
browseSort.addEventListener('change',()=>{ browsePage=1; loadBrowse(); });
document.getElementById('prev-page').addEventListener('click',()=>{ browsePage--; loadBrowse(); });
document.getElementById('next-page').addEventListener('click',()=>{ browsePage++; loadBrowse(); });
addEventListener('popstate',()=>{ clearTimeout(searchTimer); readBrowseURL(); loadBrowse(); });
readBrowseURL(); loadBrowse();
