/* Golden Football Gazette — mobile-only navigation/layout controller.
 * No DOM reparenting or rewriting existing desktop sections. Desktop keeps
 * its original appearance, functionality, order and navigation.
 */
(function(root){
'use strict';
const doc=root?.document;
if(!doc||!root.matchMedia)return;
const small=root.matchMedia('(max-width: 700px)');
const valid=new Set(['home','scores','league','gazette','more','article-one','article-two']);
const routeFromHash=Object.freeze({
  '#home':'home','#scores':'scores','#league':'league',
  '#gazette':'gazette','#more':'more',
  '#page-one':'article-one','#page-two':'article-two',
  '#espn-live':'league','#playoff-picture':'league',
  '#championship-bracket':'league','#consolation-bracket':'league',
  '#standings':'article-one','#matchups':'article-two','#waivers':'article-two',
  '#weekly-nfl':'scores'
});
const hashByView=Object.freeze({
  home:'#home',scores:'#scores',league:'#league',gazette:'#gazette',
  more:'#more','article-one':'#page-one','article-two':'#page-two'
});
function currentView(){
 return valid.has(doc.body?.dataset.gazetteMobileView)?
   doc.body.dataset.gazetteMobileView:'home';
}
function updateSelected(view){
 const selected=view.startsWith('article-')?'gazette':view;
 for(const button of doc.querySelectorAll('[data-mobile-nav]')){
   if(button.dataset.mobileNav===selected)button.setAttribute('aria-current','page');
   else button.removeAttribute('aria-current');
 }
 const forward=doc.getElementById('gazette-mobile-next-article');
 if(forward){
   const isOne=view==='article-one';
   forward.dataset.mobileTarget=isOne?'article-two':'article-one';
   forward.textContent=isOne?'Read Page Two →':'← Read Page One';
 }
}
function viewFromUrl(){
 const hash=root.location?.hash?.toLowerCase()||'';
 return routeFromHash[hash]||'home';
}
function activate(view,{push=false,scrollTarget=null}={}){
 if(!small.matches||!doc.body)return false;
 if(!valid.has(view))view='home';
 doc.body.dataset.gazetteMobileView=view;
 updateSelected(view);
 if(push&&root.history?.pushState){
   const hash=hashByView[view];
   if(root.location.hash!==hash)
     root.history.pushState({gazetteMobileView:view},'',root.location.pathname+root.location.search+hash);
 }
 if(scrollTarget){
   root.requestAnimationFrame?.(()=>{
     const target=doc.getElementById(scrollTarget)||
       (scrollTarget==='standings'?
         doc.querySelector('article[aria-label="Newspaper page one"] .table-scroll'):null);
     if(target&&target.getClientRects().length)
       target.scrollIntoView({behavior:'smooth',block:'start'});
     else root.scrollTo?.(0,0);
   });
 }else root.scrollTo?.(0,0);
 return true;
}
function refreshPreviews(){
 const slots=[
   ['Newspaper page one','gazette-mobile-feature-one-status','ESPN-verified · every 48 hours'],
   ['Newspaper page two','gazette-mobile-feature-two-status','Daily fictional fan column']
 ];
 for(const [name,id,fallback] of slots){
   const status=doc.querySelector('article[aria-label="'+name+'"] .edition-status');
   const target=doc.getElementById(id);
   const special=name==='Newspaper page one'&&
     doc.querySelector('article.governors-cup-active #governors-cup-special:not([hidden])');
   if(target)target.textContent=special?
     'Governor’s Cup history · One-time special edition':status?.textContent?.trim()||fallback;
 }
}
function moveMatchups(direction){
 if(!small.matches)return;
 const holder=doc.getElementById('espn-games');
 if(!holder)return;
 const card=holder.firstElementChild;
 const width=card?card.getBoundingClientRect().width+10:
   holder.clientWidth;
 holder.scrollBy({left:width*direction,behavior:'smooth'});
}
function handleClick(event){
 if(!small.matches)return;
 const button=event.target.closest('[data-mobile-target],[data-mobile-carousel]');
 if(!button||!button.closest('.gazette-mobile-only'))return;
 if(button.hasAttribute('data-mobile-carousel')){
   moveMatchups(button.dataset.mobileCarousel==='next'?1:-1);
   return;
 }
 const view=button.dataset.mobileTarget;
 if(!valid.has(view))return;
 const target=button.dataset.mobileScrollTarget||null;
 activate(view,{push:true,scrollTarget:target});
}
function applyLayout(){
 if(!doc.body)return;
 if(!small.matches){
   delete doc.body.dataset.gazetteMobileView;
   return;
 }
 activate(viewFromUrl());
 refreshPreviews();
}
function setup(){
 doc.addEventListener('click',handleClick);
 root.addEventListener('popstate',applyLayout);
 root.addEventListener('hashchange',applyLayout);
 if(typeof small.addEventListener==='function')small.addEventListener('change',applyLayout);
 else small.addListener?.(applyLayout);
 const paper=doc.querySelector('main.paper');
 if(paper&&root.MutationObserver){
   const monitor=new root.MutationObserver(refreshPreviews);
   monitor.observe(paper,{childList:true,subtree:true});
 }
 applyLayout();
}
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',setup,{once:true});
else setup();
if(typeof module!=='undefined'&&module.exports)
 module.exports={hashByView,routeFromHash,valid};
})(typeof window!=='undefined'?window:null);
