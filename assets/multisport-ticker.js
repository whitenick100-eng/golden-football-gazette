/* Golden Football Gazette — source-verified off-live-NFL scores and news.
 * Loaded only when the official NFL scoreboard confirms no games in progress.
 * NASCAR is sourced EXCLUSIVELY from verified NASCAR.com article links through
 * a sanitized same-origin JSON snapshot. All other eight sports keep their
 * existing ESPN scoreboards and news feeds. Never invent race positions.
 */
(function(root){
'use strict';
const BASE='https://site.api.espn.com/apis/site/v2/sports/';
const SPORTS=Object.freeze([
  {id:'NFL',path:'football/nfl',kind:'team',page:'https://www.espn.com/nfl/'},
  {id:'NBA',path:'basketball/nba',kind:'team',page:'https://www.espn.com/nba/'},
  {id:'WNBA',path:'basketball/wnba',kind:'team',page:'https://www.espn.com/wnba/'},
  {id:'PGA',path:'golf/pga',kind:'golf',page:'https://www.espn.com/golf/'},
  {id:'NCAA FB',path:'football/college-football',kind:'team',page:'https://www.espn.com/college-football/',scoreboardQuery:'scoreboard?groups=80&limit=100'},
  {id:'NCAA MEN',path:'basketball/mens-college-basketball',kind:'team',page:'https://www.espn.com/mens-college-basketball/'},
  {id:'NCAA WOMEN',path:'basketball/womens-college-basketball',kind:'team',page:'https://www.espn.com/womens-college-basketball/'},
  {id:'MLB',path:'baseball/mlb',kind:'team',page:'https://www.espn.com/mlb/'},
  {id:'NASCAR',path:'official/nascar-com',kind:'nascar-official',page:'https://www.nascar.com/'}
]);
const MAX_SCORE_AGE_MS=8*24*60*60*1000; // Weekly leagues still show last weekend's final.
const MAX_NEWS_AGE_MS=30*24*60*60*1000; // Clearly date older, offseason headlines.
const FRESH_NEWS_AGE_MS=48*60*60*1000;
const REGULAR_NEWS_AGE_MS=14*24*60*60*1000;
const FETCH_TIMEOUT_MS=9000;
const MAX_PARALLEL=4;
const CACHE_MS=5*60*1000;
// Cache each league independently so selecting one sport does not refetch all.
const leagueCache=new Map();
const SPORT_IDS=Object.freeze(['ALL',...SPORTS.map(s=>s.id)]);
function validSportSelection(id){return SPORT_IDS.includes(id)}

function espnLink(raw){
 if(typeof raw!=='string')return null;
 try{
   const u=new URL(raw);
   if(u.protocol!=='https:'||u.hostname!=='www.espn.com')return null;
   return u.href;
 }catch(_){return null}
}
// News feeds can cross-list stories from other leagues. Match the sport to
// the story itself before rendering the badge; never label an NFL/NHL article
// as NBA simply because it appeared in the NBA feed.
const ARTICLE_PATH_SPORTS=[
  [/^\/nba(?:\/|$)/,'NBA'],
  [/^\/wnba(?:\/|$)/,'WNBA'],
  [/^\/golf(?:\/|$)/,'PGA'],
  [/^\/college-football(?:\/|$)/,'NCAA FB'],
  [/^\/mens-college-basketball(?:\/|$)/,'NCAA MEN'],
  [/^\/womens-college-basketball(?:\/|$)/,'NCAA WOMEN'],
  [/^\/mlb(?:\/|$)/,'MLB'],
  [/^\/(?:racing\/nascar|nascar)(?:\/|$)/,'NASCAR'],
  [/^\/nfl(?:\/|$)/,'NFL'],
  [/^\/nhl(?:\/|$)/,'NHL'],
  [/^\/soccer(?:\/|$)/,'SOCCER']
];
const ARTICLE_SPORT_ALIASES=Object.freeze({
  nba:'NBA',wnba:'WNBA',pga:'PGA',golf:'PGA',
  collegefootball:'NCAA FB',ncaaf:'NCAA FB',cfb:'NCAA FB',
  menscollegebasketball:'NCAA MEN',ncaam:'NCAA MEN',
  womenscollegebasketball:'NCAA WOMEN',ncaaw:'NCAA WOMEN',
  mlb:'MLB',majorleaguebaseball:'MLB',nascar:'NASCAR',
  nfl:'NFL',nhl:'NHL',soccer:'SOCCER'
});
function classifyNewsSport(article,sport){
 const href=espnLink(article?.links?.web?.href);
 if(href){
   const pathname=new URL(href).pathname.toLowerCase();
   for(const [pattern,id] of ARTICLE_PATH_SPORTS){
     if(pattern.test(pathname))return id;
   }
 }
 // Use explicit league/sport metadata only. Team names or generic 'sports'
 // tags are not a reliable substitute for the article's actual category.
 const matches=new Set();
 for(const category of Array.isArray(article?.categories)?article.categories:[]){
   if(!['league','sport'].includes(String(category?.type||'').toLowerCase()))continue;
   for(const field of ['leagueId','league','description','name','slug','sport']){
     const value=category?.[field];
     if(typeof value!=='string')continue;
     const key=value.toLowerCase().replace(/[^a-z0-9]/g,'');
     if(ARTICLE_SPORT_ALIASES[key])matches.add(ARTICLE_SPORT_ALIASES[key]);
   }
 }
 if(matches.size===1)return [...matches][0];
 // When the article supplies no specific category, retain the known
 // league-specific ESPN news feed as the last-resort attribution.
 return sport.id;
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
   team:state==='in'?'LIVE':'FINAL',text:state==='in'?'ESPN verified live score':
     'FINAL · '+new Date(event.date).toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'America/New_York'}),
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
 // NASCAR never accepts the ESPN-shaped racing scoreboard path.
 if(sport?.id==='NASCAR')return [];
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
// ESPN does not expose a trustworthy, cross-sport popularity ranking in these
// public feeds. Editorial prominence, publication time and verifiable major
// news events are proxies. Never claim a story has measured high readership.
const MAJOR_NEWS=/\b(?:trades?|traded|deal|acquires?|acquired|signs?|signed|signing|contract|extension|injur(?:y|ies|ed)|ruled out|out for|season[- ]ending|fired|firing|dismissed|suspend(?:ed|sion|s)|arrested|upset|champion(?:ship|s)?|title|finals|playoffs?|postseason|record[- ]breaking|historic|milestone|retires?|retirement|draft|mvp|major award|clinches?|advances?|qualifies?|crash|pole position|tournament winner)\b/i;
const EXTRA_MAJOR=/\b(?:blockbuster|shocking|breaking|huge|historic|title|championship|national title|record[- ]breaking|first[- ]ever|sweeps?|no\.\s*1)\b/i;
const LOW_VALUE_NEWS=/\b(?:podcast|how to watch|streaming guide|betting|best bets?|prop bets?|odds|preview|predictions?|power rankings|fantasy advice|mailbag|opinion|mock draft|what to watch|watch live|daily picks?)\b/i;
function newsImportance(article,now=Date.now(),sourceIndex=0){
 const headline=String(article?.headline||'').trim();
 const published=Date.parse(article?.published||article?.lastModified||'');
 if(!headline||!Number.isFinite(published)||published>now+60*60*1000||
    now-published>MAX_NEWS_AGE_MS)return null;
 const age=now-published;
 const breaking=(/breaking/i.test(String(article?.type||''))||
    /^breaking(?:[:\s-]|$)/i.test(headline))&&age<=12*60*60*1000;
 // Avoid predictions, gambling links and other low-value filler even when
 // regular sports headlines are requested.
 if(LOW_VALUE_NEWS.test(headline)&&!breaking)return null;
 const featured=age<=FRESH_NEWS_AGE_MS&&
   (breaking||MAJOR_NEWS.test(headline)||EXTRA_MAJOR.test(headline));
 const recency=age<=6*60*60*1000?24:age<=24*60*60*1000?18:
   age<=72*60*60*1000?12:age<=REGULAR_NEWS_AGE_MS?6:1;
 const priority=(breaking?120:featured?60:0)+recency+
   Math.max(0,5-Math.max(0,sourceIndex));
 const label=breaking?'BREAKING':featured?'MAJOR NEWS':
   age<=72*60*60*1000?'LATEST NEWS':
   age<=REGULAR_NEWS_AGE_MS?'RECENT NEWS':'OLDER NEWS';
 return {priority,breaking,featured,published,age,label};
}
function newsRows(data,sport,now=Date.now()){
 if(!Array.isArray(data?.articles))return [];
 const rows=[],used=new Set();
 for(const [index,article] of data.articles.entries()){
   const signal=newsImportance(article,now,index);
   const link=espnLink(article?.links?.web?.href);
   if(!signal||!link||used.has(link))continue;
   const storySport=classifyNewsSport(article,sport);
   // NASCAR may ONLY appear through the independent NASCAR.com snapshot.
   // ESPN cross-listed NASCAR articles must not leak into All Sports either.
   if(storySport==='NASCAR'||!SPORTS.some(available=>available.id===storySport))continue;
   used.add(link);
   rows.push({sport:storySport,kind:'news',name:article.headline.trim().slice(0,110),
     team:signal.label,featured:signal.featured,
     text:'ESPN · '+new Date(signal.published).toLocaleDateString('en-US',{month:'short',day:'numeric'}),
     href:link,date:signal.published,priority:signal.priority,checked:now});
 }
 // Prefer stories actually about this selected league. Cross-listed articles
 // stay accurately labeled and may appear when this league has fewer than 4.
 // The off-season fallback is applied per article sport, not across a mixed feed.
 function pick(pool){
   const preferred=pool.some(row=>now-row.date<=REGULAR_NEWS_AGE_MS)?
     pool.filter(row=>now-row.date<=REGULAR_NEWS_AGE_MS):pool;
   const byPriority=(a,b)=>b.priority-a.priority||b.date-a.date;
   const top=preferred.filter(row=>row.featured).sort(byPriority);
   const routine=preferred.filter(row=>!row.featured).sort(byPriority);
   const chosen=[...top.slice(0,2),...routine.slice(0,2)];
   for(const row of [...top.slice(2),...routine.slice(2)]){
     if(chosen.length>=4)break;
     chosen.push(row);
   }
   return chosen.slice(0,4);
 }
 const own=pick(rows.filter(row=>row.sport===sport.id));
 const cross=pick(rows.filter(row=>row.sport!==sport.id));
 return [...own,...cross].slice(0,4);
}
function nascarLink(raw){
 if(typeof raw!=='string')return null;
 try{
   const u=new URL(raw);
   if(u.protocol!=='https:'||u.hostname!=='www.nascar.com'||u.port||
     !/^\/news-media\/20\d{2}\/(?:0[1-9]|1[0-2])\/(?:[0-2]\d|3[01])\/[a-z0-9-]+\/?$/i.test(u.pathname))
     return null;
   return 'https://www.nascar.com'+u.pathname;
 }catch(_){return null}
}
function nascarScheduleLink(raw){
 if(typeof raw!=='string')return null;
 try{
   const u=new URL(raw);
   if(u.protocol!=='https:'||u.hostname!=='www.nascar.com'||u.port||
     !/^\/nascar-cup-series\/20\d{2}\/schedule\/$/.test(u.pathname))
     return null;
   return 'https://www.nascar.com'+u.pathname;
 }catch(_){return null}
}
function nascarRaceDate(raw){
 if(typeof raw!=='string'||!/^20\d{2}-(0[1-9]|1[0-2])-([0-2]\d|3[01])$/.test(raw))return null;
 const timestamp=Date.parse(raw+'T12:00:00Z');
 return Number.isFinite(timestamp)&&new Date(timestamp).toISOString().slice(0,10)===raw?
   timestamp:null;
}
// NASCAR information is from official NASCAR.com articles and the NASCAR-owned
// cf.nascar.com Cup schedule / weekend-race results. Never touch ESPN racing.
function nascarRows(feed,now=Date.now()){
 if(feed?.schema!==1||feed.source!=='NASCAR.com'||
   feed.status!=='available'||!Array.isArray(feed.articles)||
   !Array.isArray(feed.results)||!Array.isArray(feed.upcoming))
   throw Error('Verified official NASCAR.com data snapshot unavailable');
 const fetched=Date.parse(feed.fetchedAt||'');
 if(!Number.isFinite(fetched)||fetched>now+10*60*1000||
    now-fetched>7*24*60*60*1000)
   throw Error('NASCAR.com snapshot is not recently verified');
 const news=[],scores=[],seen=new Set();
 for(const article of feed.articles.slice(0,30)){
   const link=nascarLink(article?.url);
   const title=typeof article?.title==='string'?article.title.trim():'';
   const pathDate=link&&link.match(/\/news-media\/(\d{4})\/(\d{2})\/(\d{2})\//);
   if(!link||!pathDate||!title||title.length<14||title.length>160||
     article?.type!=='news'||seen.has(link))continue;
   const canonicalDay=pathDate[1]+'-'+pathDate[2]+'-'+pathDate[3];
   if(article.date!==canonicalDay||
      article.dateBasis!=='official NASCAR.com dated article permalink')continue;
   const published=nascarRaceDate(canonicalDay);
   if(published===null||published>now+24*60*60*1000||
      now-published>MAX_NEWS_AGE_MS)continue;
   seen.add(link);
   const age=now-published;
   news.push({sport:'NASCAR',kind:'news',name:title.slice(0,110),
     team:age<=3*24*60*60*1000?'LATEST NEWS':
       age<=REGULAR_NEWS_AGE_MS?'RECENT NEWS':'OLDER NEWS',
     text:'NASCAR.com · '+new Date(published).toLocaleDateString('en-US',
       {month:'short',day:'numeric',timeZone:'UTC'}),
     href:link,date:published,priority:100-Math.floor(age/3600000),
     checked:fetched});
 }
 news.sort((a,b)=>b.date-a.date);
 for(const result of feed.results.slice(0,8)){
   const href=nascarScheduleLink(result?.url);
   const date=nascarRaceDate(result?.date);
   const race=typeof result?.race==='string'?result.race.trim():'';
   const winner=typeof result?.winner==='string'?result.winner.trim():'';
   if(!href||date===null||date>now+24*60*60*1000||
      now-date>46*24*60*60*1000||result?.status!=='final'||
      result?.verification!=='NASCAR.com official Cup weekend race results'||
      race.length<6||winner.length<3)continue;
   scores.push({sport:'NASCAR',kind:'score',name:race.slice(0,90),
     team:'FINAL',text:'Winner: '+winner.slice(0,65)+' · NASCAR.com',
     href,date,checked:fetched});
 }
 scores.sort((a,b)=>b.date-a.date);
 for(const upcoming of feed.upcoming.slice(0,8)){
   const href=nascarScheduleLink(upcoming?.url);
   const date=nascarRaceDate(upcoming?.date);
   const race=typeof upcoming?.race==='string'?upcoming.race.trim():'';
   const track=typeof upcoming?.track==='string'?upcoming.track.trim():'';
   if(!href||date===null||date<now-2*24*60*60*1000||
     date>now+400*24*60*60*1000||upcoming?.status!=='scheduled'||
     upcoming?.verification!=='NASCAR.com official Cup race schedule'||race.length<6)continue;
   news.push({sport:'NASCAR',kind:'news',name:race.slice(0,90),
     team:'UPCOMING RACE',text:'NASCAR.com · '+new Date(date).toLocaleDateString(
       'en-US',{month:'short',day:'numeric',timeZone:'UTC'})+
       (track?' · '+track.slice(0,50):''),
     href,date,priority:50,checked:fetched});
 }
 return {scores:scores.slice(0,3),news:news.slice(0,4)};
}

function mixRows(perSport,selected='ALL'){
 const rows=[],seenNews=new Set(),seenScores=new Set();
 function append(row){
   if(!row)return;
   if(selected!=='ALL'&&row.sport!==selected)return;
   if(row.kind==='news'){
     if(!row.href||seenNews.has(row.href))return;
     seenNews.add(row.href);
   }else if(row.kind==='score'){
     const key=[row.sport,row.href,row.name,row.date].join(':');
     if(seenScores.has(key))return;
     seenScores.add(key);
   }
   rows.push(row);
 }
 // All Sports remains compact (three scores + two news per league).
 // Individual tabs show up to three scores and FOUR headlines, including
 // regular reporting even when one or two breaking stories are available.
 for(const sport of SPORTS){
   if(selected!=='ALL'&&sport.id!==selected)continue;
   const feed=perSport[sport.id]||{scores:[],news:[]};
   append(feed.scores[0]);
   append(feed.scores[1]);
   append(feed.news[0]);
   append(feed.scores[2]);
   append(feed.news[1]);
   if(selected!=='ALL'){
     append(feed.news[2]);
     append(feed.news[3]);
   }
 }
 return rows.slice(0,selected==='ALL'?45:7);
}
async function fetchJSON(root,url){
 const controller=new AbortController();
 const timeout=root.setTimeout(()=>controller.abort(),FETCH_TIMEOUT_MS);
 try{
   const response=await root.fetch(url,{mode:'cors',credentials:'omit',
     cache:'no-store',signal:controller.signal});
   if(!response.ok)throw Error('Sports feed HTTP '+response.status);
   return await response.json();
 }finally{root.clearTimeout(timeout)}
}
async function load(rootWindow=root,force=false,selected='ALL'){
 const now=Date.now();
 if(!validSportSelection(selected))throw Error('Unknown sports ticker filter');
 if(!rootWindow?.fetch)throw Error('Browser fetch unavailable');
 const requested=selected==='ALL'?SPORTS:SPORTS.filter(s=>s.id===selected);
 const perSport={};
 const tasks=[];
 const checks={};
 let failures=0,successes=0;
 for(const sport of requested){
   const fromCache=leagueCache.get(sport.id);
   if(!force&&fromCache&&now-fromCache.at<CACHE_MS&&now>=fromCache.at){
     perSport[sport.id]=fromCache.feed;
     failures+=fromCache.failures;
     successes+=fromCache.successes;
   }else{
     perSport[sport.id]={scores:[],news:[]};
     checks[sport.id]={failures:0,successes:0};
     if(sport.id==='NASCAR')tasks.push({sport,kind:'nascar'});
     else tasks.push({sport,kind:'score'},{sport,kind:'news'});
   }
 }
 let cursor=0;
 async function worker(){
   while(cursor<tasks.length){
     const task=tasks[cursor++];
     const official=task.kind==='nascar';
     const endpoint=task.kind==='score'?
       (task.sport.scoreboardQuery||'scoreboard?limit=35'):'news?limit=20';
     const url=official?'data/nascar-ticker.json?ts='+now:
       BASE+task.sport.path+'/'+endpoint;
     try{
       const data=await fetchJSON(rootWindow,url);
       if(official)perSport[task.sport.id]=nascarRows(data,now);
       else if(task.kind==='score')perSport[task.sport.id].scores=scoreRows(data,task.sport,now);
       else perSport[task.sport.id].news=newsRows(data,task.sport,now);
       checks[task.sport.id].successes++;successes++;
     }catch(_){
       checks[task.sport.id].failures++;failures++;
     }
   }
 }
 await Promise.all(Array.from({length:Math.min(MAX_PARALLEL,tasks.length)},()=>worker()));
 for(const sport of requested){
   const check=checks[sport.id];
   // An outage cannot become a trusted, empty news/score cache entry.
   if(check?.successes)leagueCache.set(sport.id,{
     feed:perSport[sport.id],at:Date.now(),
     failures:check.failures,successes:check.successes
   });
 }
 // Selected league gets only its own verified scores and article topics.
 const rows=mixRows(perSport,selected);
 return {rows,checked:new Date(),partial:failures>0,sourcesAvailable:successes,
   selectedSport:selected,
   mode:selected==='ALL'?'NFL · NBA · WNBA · PGA · NCAA FB + BASKETBALL · MLB · NASCAR OFFICIAL RESULTS + NEWS':
     selected==='NASCAR'?'NASCAR · OFFICIAL NASCAR.COM RESULTS + SCHEDULE':selected+' · VERIFIED SCORES + NEWS',
   notes:failures?'Some sports feeds unavailable · Showing only verified source-backed items':
     'ESPN scores and news for other sports · NASCAR headlines exclusively from NASCAR.com'};
}
const api={SPORTS,SPORT_IDS,validSportSelection,asScore,espnLink,nascarLink,nascarRows,activeOrFinal,scoreRows,newsRows,mixRows,classifyNewsSport,newsImportance,load};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(root&&root.document)root.GazetteMultiSport=api;
})(typeof window!=='undefined'?window:null);
