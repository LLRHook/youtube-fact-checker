'use strict';
const claimExpanded = new Set();
function sourceLink(source) { const title=escapeHtml(source.title || source.domain || 'Source'); return /^https?:\/\//i.test(source.url || '') ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer nofollow">${title}${icon('link')}</a>` : `<span>${title}</span>`; }
function sourceDomain(source) { if(source.domain) return source.domain; try { return new URL(source.url).hostname; } catch(_) { return 'Source'; } }
function sourceRow(source) {
  const domain=sourceDomain(source); let hash=0; for(const c of domain) hash=(hash*31+c.charCodeAt(0))>>>0;
  const reliability={factchecker:'Fact-checker',high:'High reliability',medium:'General source',low:'User-generated'}[source.reliability];
  const stance={supports:['Supports','true','check'],refutes:['Refutes','false','cross'],context:['Context','unverifiable','transcript']}[source.stance];
  return `<li class="source-row"><span class="source-avatar" style="--avatar-hue:${hash%360}" aria-hidden="true">${escapeHtml(domain[0]?.toUpperCase() || '?')}</span><div class="source-content"><div class="source-title">${sourceLink(source)}</div><div class="source-meta"><span>${escapeHtml(domain)}</span>${reliability ? `<span class="reliability-badge">${reliability}</span>` : ''}${stance ? `<span class="pill v-${stance[1]}">${icon(stance[2])}${stance[0]}</span>` : ''}</div>${source.quote ? `<blockquote class="source-quote">“${escapeHtml(source.quote)}”</blockquote>` : ''}${source.kind==='factcheck' && source.rating ? `<p class="source-rating">Rating: ${escapeHtml(source.rating)}</p>` : ''}</div></li>`;
}
function savedVote(id,index) { try { return localStorage.getItem(`fb:${id}:${index}`); } catch(_) { return null; } }
function feedbackButtons(claim,id) {
  const selected=savedVote(id,claim.index),counts=claim.feedback || {};
  return `<span>Was this assessment helpful?</span><div class="vote-buttons">${[['yes',true,'helpful','Yes'],['no',false,'not_helpful','No']].map(([value,helpful,key,label])=>`<button class="button ghost vote-button" data-helpful="${helpful}" aria-pressed="${selected===value}">${label} <span>${Number(counts[key]) || 0}</span></button>`).join('')}</div>`;
}
function claimCard(claim,id,processing=false) {
  const index=Number(claim.index),expanded=claimExpanded.has(index),confidence=['high','medium','low'].includes(claim.confidence_label) ? claim.confidence_label : 'medium';
  const cited=(claim.sources || []).filter(s=>s.stance),other=(claim.sources || []).filter(s=>!s.stance);
  return `<article class="claim-card card v-${VERDICTS[claim.verdict] ? claim.verdict : 'unverifiable'}" id="claim-${index}" data-index="${index}"><div class="claim-header"><div class="claim-tags">${verdictPill(claim.verdict)}<button class="timestamp button ghost" data-seek="${Number(claim.timestamp_seconds)||0}" aria-label="Play from ${formatTimestamp(claim.timestamp_seconds)}">▶ ${formatTimestamp(claim.timestamp_seconds)}</button>${['guest','quoted'].includes(claim.speaker) ? `<span class="tag">${claim.speaker==='guest' ? 'Guest' : 'Quoting someone'}</span>` : ''}${claim.topic ? `<span class="tag">${escapeHtml(claim.topic)}</span>` : ''}</div><button class="claim-toggle" aria-expanded="${expanded}" aria-controls="claim-body-${index}"><span class="claim-title">${escapeHtml(claim.text)}</span><span class="claim-confidence"><span class="confidence-bars ${confidence}" aria-hidden="true"><i></i><i></i><i></i></span>${confidence[0].toUpperCase()+confidence.slice(1)} confidence <svg class="disclosure-icon" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></span><span class="claim-preview" ${expanded ? 'hidden' : ''}>${escapeHtml((claim.reasoning || '').match(/.*?[.!?](?:\s|$)/)?.[0] || claim.reasoning)}</span></button></div><div id="claim-body-${index}" class="claim-body" ${expanded ? '' : 'hidden'}>${claim.quote ? `<section><h3>What was said</h3><blockquote class="spoken-quote">“${escapeHtml(claim.quote)}”<small>${formatTimestamp(claim.timestamp_seconds)}</small></blockquote></section>` : ''}<section><h3>Assessment</h3><p>${escapeHtml(claim.reasoning)}</p></section>${claim.corrected_claim ? `<section class="correction"><h3>Correction</h3><p>${escapeHtml(claim.corrected_claim)}</p></section>` : ''}${claim.relies_on_general_knowledge ? '<p class="knowledge-note">Based on general knowledge</p>' : ''}<section><h3>Evidence</h3>${cited.length ? `<ul class="sources">${cited.map(sourceRow).join('')}</ul>` : '<p class="muted">No cited sources available for this claim.</p>'}${other.length ? `<details class="other-sources"><summary>Other sources reviewed (${other.length})</summary><ul>${other.map(s=>`<li>${sourceLink(s)}<span class="muted">${escapeHtml(sourceDomain(s))}</span></li>`).join('')}</ul></details>` : ''}</section><div class="claim-footer">${processing ? '' : `<div class="feedback">${feedbackButtons(claim,id)}</div>`}<button class="icon-button claim-copy" aria-label="Copy link to claim">${icon('link')}</button></div></div></article>`;
}
function setClaimExpanded(card,expand) {
  const index=Number(card.dataset.index); if(expand) claimExpanded.add(index); else claimExpanded.delete(index);
  card.querySelector('.claim-toggle').setAttribute('aria-expanded',String(expand)); card.querySelector('.claim-body').hidden=!expand; card.querySelector('.claim-preview').hidden=expand;
}
function wireClaims(root,claims,id,processing=false) {
  root.querySelectorAll('.claim-card').forEach(card=>{
    const claim=claims.find(c=>Number(c.index)===Number(card.dataset.index));
    card.querySelector('.claim-toggle').addEventListener('click',()=>setClaimExpanded(card,card.querySelector('.claim-toggle').getAttribute('aria-expanded')!=='true'));
    card.querySelector('[data-seek]').addEventListener('click',e=>document.dispatchEvent(new CustomEvent('claim-seek',{detail:Number(e.currentTarget.dataset.seek)})));
    card.querySelector('.claim-copy').addEventListener('click',async()=>{ try { await copyText(`${location.origin}${location.pathname}#claim-${claim.index}`); toast('Link copied'); } catch(error) { toast(error.message); } });
    card.querySelectorAll('details').forEach(details=>{ const summary=details.querySelector('summary'); summary.setAttribute('aria-expanded',String(details.open)); details.addEventListener('toggle',()=>summary.setAttribute('aria-expanded',String(details.open))); });
    if(!processing) card.querySelectorAll('.vote-button').forEach(button=>button.addEventListener('click',async()=>{
      const helpful=button.dataset.helpful==='true',value=helpful ? 'yes' : 'no',old=savedVote(id,claim.index); if(old===value) return;
      const previous={...(claim.feedback || {helpful:0,not_helpful:0})}; claim.feedback={...previous}; if(old) claim.feedback[old==='yes' ? 'helpful' : 'not_helpful']=Math.max(0,claim.feedback[old==='yes' ? 'helpful' : 'not_helpful']-1); claim.feedback[helpful ? 'helpful' : 'not_helpful']++;
      card.querySelectorAll('.vote-button').forEach(b=>{ b.disabled=true; b.setAttribute('aria-pressed',String(b===button)); b.querySelector('span').textContent=claim.feedback[b.dataset.helpful==='true' ? 'helpful' : 'not_helpful']; });
      try { await api(`/api/videos/${encodeURIComponent(id)}/claims/${claim.index}/feedback`,{method:'POST',body:{helpful}}); try { localStorage.setItem(`fb:${id}:${claim.index}`,value); } catch(_) {} }
      catch(error) { claim.feedback=previous; card.querySelectorAll('.vote-button').forEach(b=>{ b.setAttribute('aria-pressed',String((b.dataset.helpful==='true' ? 'yes' : 'no')===old)); b.querySelector('span').textContent=previous[b.dataset.helpful==='true' ? 'helpful' : 'not_helpful']; }); toast(error.message); }
      finally { card.querySelectorAll('.vote-button').forEach(b=>b.disabled=false); }
    }));
  });
}
