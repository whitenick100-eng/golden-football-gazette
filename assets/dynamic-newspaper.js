/* The Golden Football Gazette: automated two-page editorial presentation.
 * Page One: ESPN facts only, published every >=48h after source verification.
 * Page Two: daily factual fixtures/waivers plus EXPLICITLY FICTIONAL commentary.
 * Never turn invented interviews into purported statements from real fans.
 */
(function(root){
'use strict';
const DOC=root?.document;
const URL='data/gazette-pages.json';
function node(tag,klass,text){
 const el=DOC.createElement(tag);
 if(klass)el.className=klass;
 if(text!==undefined&&text!==null)el.textContent=String(text);
 return el;
}
function date(value){
 if(!value)return 'Source date unavailable';
 const v=new Date(value);
 return Number.isNaN(v.getTime())?'Date not verified':
   v.toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',
      year:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
}
function record(team){
 if(!Number.isInteger(team?.wins)||!Number.isInteger(team?.losses))return '—';
 return team.wins+'–'+team.losses+(team.ties?'–'+team.ties:'');
}
function section(title){
 const x=node('section','section');
 x.append(node('h3',null,title));
 return x;
}
function paragraph(parent,text,klass){
 parent.append(node('p',klass||null,text));
}
function list(parent,items,map){
 const el=node('ul','edition-list');
 for(const item of items){
   const child=node('li');
   child.textContent=map(item);
   el.append(child);
 }
 parent.append(el);
}
function replaceArchived(page){
 for(const old of [...page.querySelectorAll(':scope > section.section')])old.remove();
 for(const old of [...page.querySelectorAll(':scope > .edition-archive-warning')])old.remove();
 const previous=page.querySelector('.edition-status');
 if(previous)previous.remove();
}
function meta(page,kind,source){
 const p=node('p','edition-status',kind+' · '+source);
 page.querySelector('h2')?.after(p);
}
function renderPageOne(data){
 const page=DOC.querySelector('article[aria-label="Newspaper page one"]');
 if(!page)return;
 if(data?.status!=='verified'||!Array.isArray(data.standings)||
    data.standings.length!==10)return; // Keep clearly labeled archival fallback.
 replaceArchived(page);
 const lastUpdated=new Date(data.publishedAt);
 const delayed=Number.isFinite(lastUpdated.getTime())&&
   Date.now()-lastUpdated.getTime()>48*60*60*1000;
 meta(page,delayed?'Earlier verified ESPN league report · refresh delayed':
   'Verified ESPN League Report · 48-hour edition',
   'Published '+date(data.publishedAt)+' · ESPN checked '+date(data.sourceAt));
 const intro=section(data.headline||'League Report');
 paragraph(intro,'The factual league record below reflects ESPN fantasy league '+data.leagueId+
   ', season '+data.season+', current scoring period '+data.currentWeek+
   '. Statistics are refreshed on a 48-hour cycle, subject to ESPN source availability.');
 if(data.leader?.name)paragraph(intro,'Current standings leader: '+data.leader.name+
   ' ('+record(data.leader)+').');
 page.append(intro);
 const standings=section('ESPN League Standings · Verified Snapshot');
 const scroll=node('div','table-scroll'),table=node('table'),thead=node('thead'),head=node('tr');
 for(const t of ['Position','Fantasy Team','Record','Points For']){
   const cell=node('th',null,t);head.append(cell);
 }
 thead.append(head);table.append(thead);
 const tbody=node('tbody');
 for(const t of data.standings){
   const row=node('tr');
   const cols=[t.position,t.name,record(t),
     Number.isFinite(t.pointsFor)?Number(t.pointsFor).toFixed(2):'—'];
   for(const col of cols)row.append(node('td',null,col));
   tbody.append(row);
 }
 table.append(tbody);scroll.append(table);standings.append(scroll);
 paragraph(standings,'Positions reflect the ESPN standings snapshot. They are not automatically confirmed playoff seeds.','small');
 page.append(standings);
 const results=section('Latest ESPN-Confirmed Fantasy Results');
 if(Array.isArray(data.finals)&&data.finals.length){
   paragraph(results,'Fantasy Week '+data.latestFinalWeek+' · completed matchups with ESPN-confirmed winners and reported final scores.');
   list(results,data.finals,g=>g.away+' '+Number(g.awayPoints).toFixed(2)+
     ' — '+g.home+' '+Number(g.homePoints).toFixed(2)+
     ' · Winner: '+g.winner);
 }else paragraph(results,'No completed matchup scores passed the ESPN verification checks in this edition.');
 page.append(results);
 const facts=section('Performance & Championship Race · Verified Facts');
 if(data.topPerformer?.name){
   paragraph(facts,'Rostered player leaderboard, Week '+data.topPerformer.week+
     ': '+data.topPerformer.name+' · '+Number(data.topPerformer.points).toFixed(2)+
     ' ESPN fantasy points. This is not necessarily the highest-scoring player in the entire NFL.');
 }
 if(data.lastPlace?.name){
   paragraph(facts,'The team currently last in the ESPN standings snapshot is '+
     data.lastPlace.name+' ('+record(data.lastPlace)+
     '). This does not establish who will receive the Golden Toilet trophy.');
 }
 paragraph(facts,data.notice||'Standings and postseason conclusions require official ESPN confirmation.','small');
 page.append(facts);
}
function renderPageTwo(data){
 const page=DOC.querySelector('article[aria-label="Newspaper page two"]');
 if(!page||data?.status!=='available')return;
 replaceArchived(page);
 meta(page,'Daily edition · '+data.writer,'Published '+date(data.publishedAt));
 const intro=section(data.title||'The Daily Sideline');
 paragraph(intro,data.fictionNotice,'edition-fiction-note');
 paragraph(intro,data.banter,'edition-banter');
 page.append(intro);
 const games=section('Upcoming ESPN Fantasy Fixtures');
 if(Array.isArray(data.fixtures)&&data.fixtures.length){
   paragraph(games,'Week '+data.fixtureWeek+' · ESPN-listed matchups; no outcome predicted as fact.');
   list(games,data.fixtures,g=>g.away+' vs. '+g.home);
 }else paragraph(games,'No future matchups could be verified from ESPN for the current scoring period.');
 page.append(games);
 const waivers=section('Fantasy Waiver & Acquisition Desk');
 if(Array.isArray(data.waivers)&&data.waivers.length){
   list(waivers,data.waivers,x=>x.team+' · '+x.acquisitions+
     ' ESPN-executed addition'+(x.acquisitions===1?'':'s')+' · scoring period '+x.week);
 }
 paragraph(waivers,data.waiverNote||'No independently verified fantasy acquisitions to report.','small');
 page.append(waivers);
 const race=section('Championship & Golden Toilet Watch');
 paragraph(race,data.championship||'Official championship seedings unavailable.');
 paragraph(race,data.consolation||'Final consolation positions not yet established.');
 paragraph(race,'Standings statements above are factual where ESPN verified; commentary below is entirely fictional.','small');
 page.append(race);
 const fans=section('Supporters’ Corner · Imagined Fan Interviews');
 paragraph(fans,'The following are invented supporters and invented quotes for all ten league teams. They are professional sports satire—not conversations with actual fans, participants or team owners.','edition-fiction-note');
 const wrap=node('div','edition-fan-grid');
 for(const fan of Array.isArray(data.interviews)?data.interviews:[]){
   if(fan?.fictional!==true)continue;
   const card=node('div','edition-fan-quote');
   card.append(node('strong',null,fan.team));
   card.append(node('blockquote',null,'“'+fan.quote+'”'));
   card.append(node('span','small','— '+fan.fan+', fictional supporter'));
   wrap.append(card);
 }
 fans.append(wrap);page.append(fans);
 const closer=section('From the Sideline');
 paragraph(closer,data.closing,'edition-banter');
 paragraph(closer,'Adrian Mercer is a fictional columnist persona. Only explicitly dated ESPN data is treated as verified; all satire, fan voices and dramatic opinions are invented.','small');
 page.append(closer);
}
async function refresh(){
 if(!DOC)return;
 try{
   const response=await root.fetch(URL+'?t='+Date.now(),{cache:'no-store'});
   if(!response.ok)throw Error('Edition feed unavailable');
   const data=await response.json();
   if(data?.schema!==1||String(data.leagueId)!=='1413446022'||data.season!==2026)
     throw Error('Edition identity mismatch');
   renderPageOne(data.pageOne);
   renderPageTwo(data.pageTwo);
   root.GazetteEditionState={
     pageOnePublishedAt:data.pageOne?.publishedAt||null,
     pageTwoPublishedAt:data.pageTwo?.publishedAt||null
   };
 }catch(error){
   console.warn('Newspaper edition fetch:',error.message);
   for(const page of DOC.querySelectorAll('article.page')){
     if(page.querySelector('.edition-status'))continue;
     meta(page,'Historical archive · New live edition temporarily unavailable',
       'These older static sections are not updated ESPN reports.');
   }
 }
}
// One-time owner-requested historical feature. Absolute timestamps use EST.
const CUP_START=Date.parse('2026-11-28T00:00:00-05:00');
const CUP_END=Date.parse('2026-11-29T07:00:00-05:00');
function isRivalryEdition(now=Date.now()){
 return Number.isFinite(now)&&now>=CUP_START&&now<CUP_END;
}
let cupTimer=null;
function syncRivalryEdition(){
 if(!DOC)return;
 const special=DOC.getElementById('governors-cup-special');
 const page=DOC.querySelector('article[aria-label="Newspaper page one"]');
 if(!special||!page)return;
 const active=isRivalryEdition();
 const wasActive=page.classList.contains('governors-cup-active');
 const heading=page.querySelector('h2');
 page.classList.toggle('governors-cup-active',active);
 special.hidden=!active;
 if(heading&&active!==wasActive)heading.textContent=active?
   '🏈 Page One · Governor’s Cup Special Edition':'🏆 Page One · League Report';
 if(cupTimer!==null){root.clearTimeout(cupTimer);cupTimer=null;}
 if(active)cupTimer=root.setTimeout(syncRivalryEdition,Math.max(1,CUP_END-Date.now()));
 if(wasActive&&!active)refresh(); // Restore the latest available ESPN report, or retain the labeled fallback.
}
const api={date,record,renderPageOne,renderPageTwo,refresh,isRivalryEdition};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(DOC){
 syncRivalryEdition();
 refresh();
 DOC.addEventListener('visibilitychange',()=>{if(!DOC.hidden)syncRivalryEdition();});
 root.addEventListener('pageshow',syncRivalryEdition);
}
})(typeof window!=='undefined'?window:null);
