/* Golden Football Gazette — source-verified non-NFL scores and news.
 * Loaded only when the official NFL scoreboard confirms no games in progress.
 * Every sport uses an ESPN scoreboard and news feed; no estimates or fabricated
 * headlines, winners, scores, or racing/golf positions are allowed.
 */
(function(root){
'use strict';
const BASE='https://site.api.espn.com/apis/site/v2/sports/';
const SPORTS=Object.freeze([
  {id:'NBA',path:'basketball/nba',kind:'team',page:'https://www.espn.com/nba/'},
  {id:'WNBA',path:'basketball/wnba',kind:'team',page:'https://www.espn.com/wnba/'},
  {id:'PGA',path:'golf/pga',kind:'golf',page:'https://www.espn.com/golf/'},
  {id:'NCAA FB',path:'football/college-football',kind:'team',page:'https://www.espn.com/college-football/',scoreboardQuery:'scoreboard?groups=80&limit=100'},
  {id:'NCAA MEN',path:'basketball/mens-college-basketball',kind:'team',page:'https://www.espn.com/mens-college-basketball/'},
  {id:'NCAA WOMEN',path:'basketball/womens-college-basketball',kind:'team',page:'https://www.espn.com/womens-college-basketball/'},
  {id:'MLB',path:'baseball/mlb',kind:'team',page:'https://www.espn.com/mlb/'},
  {id:'NASCAR',path:'racing/nascar-premier',kind:'racing',page:'https://www.espn.com/racing/nascar/'}
]);
const MAX_SCORE_AGE_MS=72*60*60*1000;
const MAX_NEWS_AGE_MS=7*24*60*60*1000;
const FETCH_TIMEOUT_MS=9000;
const MAX_PARALLEL=4;
const CACHE_MS=5*60*1000;
let cached=null,cachedAt=0;

function espnLink(raw){
 if(typeof raw!=='string')return null;
 try{
   const u=new URL(raw);
   if(u.protocol!=='https:'||u.hostname!=='www.espn.com')return null;
   return u.href;
 }catch(_){return null}
}
function eventLink(event,sport){
 for(const link of event?.links||[]){
   const url=espnLink(link?.href);
   if(url)return url;
 }
 return sport.page;
}
function asScore(value){
 if(value===undefined||value===null||value==='')return null;
 if(typeof value!=='number'&&typeof value!=='string')return null;
 const v=Number(value);
 return Number.isFinite(v)&&v>=0&&v<=500?String(value):null;
}
function activeOrFinal(event,now){
 const state=event?.status?.type?.state;
 if(!['in','post'].includes(state))return null;
 const d=Date.parse(event?.date||'');
 if(!Number.isFinite(d)||d>now+30*60*1000||now-d>MAX_SCORE_AGE_MS)return null;
 return state;
}
function teamScore(event,sport,state,now){
 const c=event?.competitions?.[0];
 if(!Array.isArray(c?.competitors))return null;
 const home=c.competitors.find(t=>t.homeAway==='home');
 const away=c.competitors.find(t=>t.homeAway==='away');
 const h=asScore(home?.score),a=asScore(away?.score);
 const hname=home?.team?.abbreviation||home?.team?.shortDisplayName;
 const aname=away?.team?.abbreviation||away?.team?.shortDisplayName;
 if(h===null||a===null||!hname||!aname)return null;
 return {sport:sport.id,kind:'score',name:String(aname).slice(0,20)+' '+a+
   ' — '+String(hname).slice(0,20)+' '+h,
   team:state==='in'?'LIVE':'FINAL',text:'ESPN verified '+(state==='in'?'live score':'final score'),
   href:eventLink(event,sport),date:Date.parse(event.date),checked:now};
}
function individualResult(event,sport,state,now){
 const c=event?.competitions?.[0];
 if(!Array.isArray(c?.competitors)||!c.competitors.length)return null;
 // ESPN publishes competitive rank as order; never infer a rank from list order.
 const leaders=c.competitors.filter(p=>Number.isInteger(p?.order)&&p.order>=1)
   .sort((a,b)=>a.order-b.order);
 const leader=leaders[0];
 if(!leader||leader.order!==1||!leader.athlete?.displayName)return null;
 const name=String(leader.athlete.displayName).slice(0,65);
 const tournament=String(event?.shortName||event?.name||sport.id).slice(0,65);
 let result;
 if(sport.kind==='golf'){
   const score=typeof leader.score==='string'||typeof leader.score==='number'?
     String(leader.score):'';
   if(!score.trim())return null; // No posted round/tournament score.
   result=name+' '+score;
 }else{
   result=name+' · P1';
 }
 return {sport:sport.id,kind:'score',name:tournament,
   team:state==='in'?'LIVE LEADER':'RESULT',
   text:result,href:eventLink(event,sport),date:Date.parse(event.date),checked:now};
}
function scoreRows(data,sport,now=Date.now()){
 if(!data||!Array.isArray(data.events))return [];
 const rows=[];
 for(const event of data.events.slice(0,65)){
   const state=activeOrFinal(event,now);
   if(!state)continue;
   const row=sport.kind==='team'?teamScore(event,sport,state,now):
     individualResult(event,sport,state,now);
   if(row)rows.push(row);
 }
 return rows.sort((a,b)=>Number(b.team.startsWith('LIVE'))-
   Number(a.team.startsWith('LIVE'))||b.date-a.date).slice(0,3);
}
function newsRows(data,sport,now=Date.now()){
 if(!Array.isArray(data?.articles))return [];
 const rows=[];
 const used=new Set();
 for(const article of data.articles){
   const headline=article?.headline;
   const published=Date.parse(article?.published||article?.lastModified||'');
   const link=espnLink(article?.links?.web?.href);
   if(!link||typeof headline!=='string'||!headline.trim()||used.has(link)||
      !Number.isFinite(published)||published>now+60*60*1000||
      now-published>MAX_NEWS_AGE_MS)continue;
   used.add(link);
   const verifiedBreaking=/breaking/i.test(String(article.type||''))||
     /^breaking[:\s-]/i.test(headline);
   rows.push({sport:sport.id,kind:'news',name:headline.trim().slice(0,110),
     team:verifiedBreaking?'BREAKING':'LATEST NEWS',
     text:'ESPN · '+new Date(published).toLocaleDateString('en-US',{month:'short',day:'numeric'}),
     href:link,date:published,checked:now});
 }
 return rows.sort((a,b)=>b.date-a.date).slice(0,2);
}
function mixRows(perSport){
 const rows=[];
 // Round-robin prevents NBA/NCAA scores from drowning out golf, NASCAR,
 // WNBA, or genuine breaking news from other sports.
 for(let index=0;index<3;index++){
   for(const sport of SPORTS){
     const feed=perSport[sport.id]||{scores:[],news:[]};
     if(index===0&&feed.scores[0])rows.push(feed.scores[0]);
     if(index===0&&feed.news[0])rows.push(feed.news[0]);
     if(index===1&&feed.scores[1])rows.push(feed.scores[1]);
     if(index===1&&feed.news[1])rows.push(feed.news[1]);
     if(index===2&&feed.scores[2])rows.push(feed.scores[2]);
   }
 }
 return rows.slice(0,28);
}
async function fetchJSON(root,url){
 const controller=new AbortController();
 const timeout=root.setTimeout(()=>controller.abort(),FETCH_TIMEOUT_MS);
 try{
   const response=await root.fetch(url,{mode:'cors',credentials:'omit',
     cache:'no-store',signal:controller.signal});
   if(!response.ok)throw Error('ESPN response HTTP '+response.status);
   return await response.json();
 }finally{root.clearTimeout(timeout)}
}
async function load(rootWindow=root,force=false){
 const now=Date.now();
 if(!force&&cached&&now>=cachedAt&&now-cachedAt<CACHE_MS)return cached;
 if(!rootWindow?.fetch)throw Error('Browser fetch unavailable');
 const perSport=Object.fromEntries(SPORTS.map(s=>[s.id,{scores:[],news:[]}]));
 const tasks=SPORTS.flatMap(s=>[{sport:s,kind:'score'},{sport:s,kind:'news'}]);
 let cursor=0,failures=0,successes=0;
 async function worker(){
   while(cursor<tasks.length){
     const task=tasks[cursor++];
     // Group 80 covers FBS college football; other leagues keep their usual feed.
     const endpoint=task.kind==='score'?(task.sport.scoreboardQuery||'scoreboard?limit=35'):'news?limit=8';
     const url=BASE+task.sport.path+'/'+endpoint;
     try{
       const data=await fetchJSON(rootWindow,url);
       if(task.kind==='score')perSport[task.sport.id].scores=scoreRows(data,task.sport,now);
       else perSport[task.sport.id].news=newsRows(data,task.sport,now);
       successes++;
     }catch(_){failures++}
   }
 }
 await Promise.all(Array.from({length:MAX_PARALLEL},()=>worker()));
 const result={rows:mixRows(perSport),checked:new Date(),partial:failures>0,
   sourcesAvailable:successes,mode:'NBA · WNBA · PGA · NCAA FB + BASKETBALL · MLB · NASCAR SCORES + NEWS',
   notes:failures?'Some ESPN feeds unavailable · Showing verified items only':
     'Live and final scores · recent ESPN headlines · automatic updates'};
 // Don't cache complete outages; allow the next visible poll to retry.
 if(successes){cached=result;cachedAt=Date.now();}
 return result;
}
const api={SPORTS,asScore,espnLink,activeOrFinal,scoreRows,newsRows,mixRows,load};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(root&&root.document)root.GazetteMultiSport=api;
})(typeof window!=='undefined'?window:null);
